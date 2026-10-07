Algorithms
==============================================================================

This page lists every optimization algorithm shipped with pymoo. It is kept in
sync with the algorithm portfolio by ``tests/test_api_reference.py`` — adding a new
algorithm without listing it here fails that test.


Single-objective
------------------------------------------------------------------------------

.. autoclass:: pymoo.algorithms.soo.nonconvex.ga.GA
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.ga_niching.NicheGA
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.de.DE
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.es.ES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.brkga.BRKGA
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.nelder.NelderMead
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.pattern.PatternSearch
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.cmaes.CMAES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.cmaes.SimpleCMAES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.cmaes.BIPOPCMAES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.isres.ISRES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.sres.SRES
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.pso.PSO
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.pso_ep.EPPSO
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.g3pcx.G3PCX
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.nrbo.NRBO
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.direct.DIRECT
    :noindex:

.. autoclass:: pymoo.algorithms.soo.nonconvex.random_search.RandomSearch
    :noindex:


Multi-objective
------------------------------------------------------------------------------

.. autoclass:: pymoo.algorithms.moo.nsga2.NSGA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.rnsga2.RNSGA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.nsga3.NSGA3
    :noindex:

.. autoclass:: pymoo.algorithms.moo.unsga3.UNSGA3
    :noindex:

.. autoclass:: pymoo.algorithms.moo.rnsga3.RNSGA3
    :noindex:

.. autoclass:: pymoo.algorithms.moo.moead.MOEAD
    :noindex:

.. autoclass:: pymoo.algorithms.moo.moead.ParallelMOEAD
    :noindex:

.. autoclass:: pymoo.algorithms.moo.age.AGEMOEA
    :noindex:

.. autoclass:: pymoo.algorithms.moo.age2.AGEMOEA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.ctaea.CTAEA
    :noindex:

.. autoclass:: pymoo.algorithms.moo.sms.SMSEMOA
    :noindex:

.. autoclass:: pymoo.algorithms.moo.rvea.RVEA
    :noindex:

.. autoclass:: pymoo.algorithms.moo.kgb.KGB
    :noindex:

.. autoclass:: pymoo.algorithms.moo.spea2.SPEA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.dnsga2.DNSGA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.pinsga2.PINSGA2
    :noindex:

.. autoclass:: pymoo.algorithms.moo.mopso_cd.MOPSO_CD
    :noindex:

.. autoclass:: pymoo.algorithms.moo.cmopso.CMOPSO
    :noindex:

.. autoclass:: pymoo.algorithms.moo.gde3.GDE3
    :noindex:

.. autoclass:: pymoo.algorithms.moo.nsde.NSDE
    :noindex:

.. autoclass:: pymoo.algorithms.moo.nsder.NSDER
    :noindex:

.. autoclass:: pymoo.algorithms.moo.omni.OmniOptimizer
    :noindex:
