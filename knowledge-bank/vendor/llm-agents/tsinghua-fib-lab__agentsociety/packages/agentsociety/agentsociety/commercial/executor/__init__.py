"""
Commercial Executor Module

Provides Kubernetes-based execution for AgentSociety commercial version.
"""

from .kubernetes import KubernetesExecutor

__all__ = ["KubernetesExecutor", "get_kubernetes_executor"]

def get_kubernetes_executor(config):
    """Get Kubernetes executor instance"""
    if not config.get('enabled', False):
        return None
    
    search_paths = config.get('config_paths', [])
    return KubernetesExecutor(search_paths) 
