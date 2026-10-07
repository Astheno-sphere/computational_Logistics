"""
A clear version of the simulation.
"""

from typing import Union


from ..configs import (
    Config,
    IndividualConfig,
)
from .simulationengine import SimulationEngine
from .individualengine import IndividualEngine

__all__ = ["AgentSociety"]


class AgentSociety:
    """
    Factory class for creating simulation engines based on configuration type.
    
    - **Description**:
        - A factory class that creates and returns the appropriate engine instance
        based on the configuration type provided.
        - Returns SimulationEngine for Config type
        - Returns TaskSolverEngine for SolverConfig type
    """
    
    @staticmethod
    def create(
        config: Union[Config, IndividualConfig],
        tenant_id: str = "",
    ) -> Union[SimulationEngine, IndividualEngine]:
        """
        Create and return the appropriate engine instance based on configuration type.
        
        - **Description**:
            - Factory method that creates the appropriate engine instance based on the
            configuration type provided.
            - For Config type: returns SimulationEngine instance
            - For IndividualConfig type: returns IndividualEngine instance
            
        - **Args**:
            - `config` (Union[Config, IndividualConfig]): The configuration object that determines
            which engine to create.
            - `tenant_id` (str, optional): The tenant ID for the engine. Defaults to "".
            
        - **Returns**:
            - `Union[SimulationEngine, IndividualEngine]`: The appropriate engine instance
            based on the configuration type.
            
        - **Raises**:
            - `ValueError`: If the configuration type is not supported.
        """
        if isinstance(config, Config):
            return SimulationEngine(config, tenant_id)
        elif isinstance(config, IndividualConfig):
            return IndividualEngine(config, tenant_id)
        else:
            raise ValueError(f"Invalid config type: {type(config)}. Expected Config or IndividualConfig.")

    def __init__(
        self,
        config: Union[Config, IndividualConfig],
        tenant_id: str = "",
    ) -> None:
        """
        Initialize AgentSociety factory class.
        
        - **Description**:
            - This constructor is kept for backward compatibility but is deprecated.
            - Use AgentSociety.create() static method instead.
            
        - **Args**:
            - `config` (Union[Config, IndividualConfig]): The configuration object.
            - `tenant_id` (str, optional): The tenant ID. Defaults to "".
        """
        import warnings
        warnings.warn(
            "AgentSociety constructor is deprecated. Use AgentSociety.create() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # For backward compatibility, delegate to the factory method
        engine = self.create(config, tenant_id)
        
        # Copy all attributes from the engine to this instance
        for attr_name in dir(engine):
            if not attr_name.startswith('_'):
                attr_value = getattr(engine, attr_name)
                if not callable(attr_value) or isinstance(attr_value, property):
                    setattr(self, attr_name, attr_value)
        
        # Store the engine instance for method delegation
        self._engine = engine

    def __getattr__(self, name):
        """
        Delegate attribute access to the underlying engine instance.
        
        - **Description**:
            - Delegates any attribute access to the underlying engine instance
            for backward compatibility.
            
        - **Args**:
            - `name` (str): The name of the attribute to access.
            
        - **Returns**:
            - The attribute value from the underlying engine.
        """
        if hasattr(self, '_engine'):
            return getattr(self._engine, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
