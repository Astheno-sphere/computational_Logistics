"""MO-CMA-ES — Multi-Objective Covariance Matrix Adaptation Evolution Strategy."""

import numpy as np

from pymoo.algorithms.moo.sms import LeastHypervolumeContributionSurvival
from pymoo.core.algorithm import Algorithm
from pymoo.core.population import Population
from pymoo.docs import parse_doc_string
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.util.display.multi import MultiObjectiveOutput
from pymoo.util.normalization import ZeroToOneNormalization


class MOCMAES(Algorithm):
    """Multi-Objective CMA-ES (Igel, Hansen & Roth, 2007).

    Maintains a population of ``pop_size`` elitist (1+1)-CMA-ES individuals — each
    with its own step size, covariance matrix and success rate — and selects the
    next generation from the combined parent+offspring set by non-dominated sorting
    with hypervolume contribution as the secondary criterion. Covariance-matrix
    adaptation gives each individual rotation and scale invariance; the
    hypervolume-based selection drives spread along the Pareto front.

    The strategy parameters follow the reference implementation (DEAP). The search
    runs in a ``[0, 1]`` normalized decision space so the initial step size is
    problem-scale independent.
    """

    def __init__(self, pop_size=100, sigma=0.2, sampling=FloatRandomSampling(),
                 output=MultiObjectiveOutput(), **kwargs):
        """Initialize MO-CMA-ES.

        Args:
            pop_size: Number of parallel (1+1)-CMA-ES individuals (mu).
            sigma: Initial step size in the normalized ``[0, 1]`` decision space.
            sampling: Sampling used for the initial population.
            output: Display output used to report progress during the run.
            **kwargs: Additional keyword arguments forwarded to ``Algorithm``.
        """
        super().__init__(output=output, **kwargs)
        self.pop_size = pop_size
        self.sigma0 = sigma
        self.sampling = sampling
        self.norm = None
        self.survival = LeastHypervolumeContributionSurvival()

        # per-individual CMA state (set up after the initial population)
        self.parents = None
        self.par_Xn = None
        self.sigma = None
        self.C = None
        self.pc = None
        self.psucc = None

    def _setup(self, problem, **kwargs):
        n = problem.n_var
        self.norm = ZeroToOneNormalization(problem.xl, problem.xu)
        # strategy parameters (functions of the dimension)
        self.ptarg = 1.0 / (5.0 + 0.5)
        self.d = 1.0 + n / 2.0
        self.cp = self.ptarg / (2.0 + self.ptarg)
        self.cc = 2.0 / (n + 2.0)
        self.ccov = 2.0 / (n**2 + 6.0)
        self.pthresh = 0.44

    def _initialize_infill(self):
        return self.sampling(self.problem, self.pop_size, random_state=self.random_state)

    def _initialize_advance(self, infills=None, **kwargs):
        n = self.problem.n_var
        mu = self.pop_size
        self.parents = infills
        self.par_Xn = self.norm.forward(infills.get("X"))
        self.sigma = np.full(mu, self.sigma0, dtype=float)
        self.C = np.array([np.eye(n) for _ in range(mu)])
        self.pc = np.zeros((mu, n))
        self.psucc = np.full(mu, self.ptarg, dtype=float)
        self.pop = infills

    def _cholesky(self, C):
        try:
            return np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            return np.linalg.cholesky(C + 1e-12 * np.eye(C.shape[0]))

    def _infill(self):
        mu, n = self.pop_size, self.problem.n_var
        off_Xn = np.empty((mu, n))
        for i in range(mu):
            z = self.random_state.standard_normal(n)
            step = self.sigma[i] * (self._cholesky(self.C[i]) @ z)
            off_Xn[i] = np.clip(self.par_Xn[i] + step, 0.0, 1.0)
        self._off_Xn = off_Xn
        return Population.new(X=self.norm.backward(off_Xn))

    def _advance(self, infills=None, **kwargs):
        mu = self.pop_size
        off = infills

        # elitist (mu+mu) selection: keep the best mu of parents+offspring by
        # non-dominated sorting + hypervolume contribution (reuse SMS-EMOA's
        # survival). Tag each candidate so we can map survivors back to state.
        merged = Population.merge(self.parents, off)
        merged.set("cma_idx", np.arange(2 * mu))
        survivors = self.survival.do(self.problem, merged, n_survive=mu,
                                     random_state=self.random_state)
        chosen = survivors.get("cma_idx").astype(int)
        chosen_set = set(chosen.tolist())

        # combined (Q) state: offspring inherit their parent's state
        Qsigma = np.concatenate([self.sigma, self.sigma])
        Qpsucc = np.concatenate([self.psucc, self.psucc])
        QC = np.concatenate([self.C, self.C])
        Qpc = np.concatenate([self.pc, self.pc])
        QXn = np.vstack([self.par_Xn, self._off_Xn])

        cp, ptarg, d = self.cp, self.ptarg, self.d
        cc, ccov, pthresh = self.cc, self.ccov, self.pthresh
        for i in range(mu):
            succ = 1.0 if (mu + i) in chosen_set else 0.0
            for j in (i, mu + i):  # update parent i and its offspring the same way
                Qpsucc[j] = (1.0 - cp) * self.psucc[i] + cp * succ
                Qsigma[j] = self.sigma[i] * np.exp((Qpsucc[j] - ptarg) / (d * (1.0 - ptarg)))
            # only the offspring adapts its covariance, from the mutation step
            step = (self._off_Xn[i] - self.par_Xn[i]) / self.sigma[i]
            o = mu + i
            if Qpsucc[o] < pthresh:
                Qpc[o] = (1.0 - cc) * self.pc[i] + np.sqrt(cc * (2.0 - cc)) * step
                QC[o] = (1.0 - ccov) * self.C[i] + ccov * np.outer(Qpc[o], Qpc[o])
            else:
                Qpc[o] = (1.0 - cc) * self.pc[i]
                QC[o] = (1.0 - ccov) * self.C[i] + ccov * (
                    np.outer(Qpc[o], Qpc[o]) + cc * (2.0 - cc) * self.C[i]
                )

        self.sigma = Qsigma[chosen]
        self.psucc = Qpsucc[chosen]
        self.C = QC[chosen]
        self.pc = Qpc[chosen]
        self.par_Xn = QXn[chosen]

        self.pop = survivors
        self.parents = self.pop


parse_doc_string(MOCMAES.__init__)
