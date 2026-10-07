use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// A cheap, cloneable shutdown signal shared between the stdio event loop and
/// the signal handlers.
///
/// The first caller to [`Shutdown::trigger`] wins; every observer sees the same
/// value afterwards. Backing the runtime shutdown with this keeps "exit now" a
/// single decision point instead of scattered flags, and it doubles as the
/// unified cancellation token described in the process-lifecycle requirements:
/// any long-lived tokio task should select on a watch/token derived from this
/// signal, while the runtime's bounded `shutdown_timeout` cancels everything
/// else when this is triggered.
#[derive(Clone, Default)]
pub struct Shutdown(Arc<AtomicBool>);

impl Shutdown {
    pub fn new() -> Self {
        Self::default()
    }

    /// Mark the process as shutting down. Idempotent.
    pub fn trigger(&self) {
        self.0.store(true, Ordering::SeqCst);
    }

    /// Whether a shutdown has been requested.
    pub fn is_triggered(&self) -> bool {
        self.0.load(Ordering::SeqCst)
    }
}
