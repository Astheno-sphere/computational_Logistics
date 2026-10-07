import asyncio
from collections.abc import Sequence
from enum import Enum
from typing import Any, Literal, Optional, Union, cast

import grpc
import pycityproto.city.economy.v2.economy_pb2 as economyv2
import pycityproto.city.economy.v2.org_service_pb2 as org_service
import pycityproto.city.economy.v2.org_service_pb2_grpc as org_grpc
from google.protobuf.json_format import MessageToDict

from ...logger import get_logger

__all__ = [
    "EconomyClient",
]


class EconomyEntityType(int, Enum):
    Unspecified = 0
    Agent = 1
    Bank = 2
    Firm = 3
    Government = 4
    NBS = 5


def _create_aio_channel(server_address: str, secure: bool = False) -> grpc.aio.Channel:
    """
    Create a gRPC asynchronous channel.

    - **Args**:
        - `server_address` (`str`): The address of the server to connect to.
        - `secure` (`bool`, optional): Whether to use a secure connection. Defaults to `False`.

    - **Returns**:
        - `grpc.aio.Channel`: A gRPC asynchronous channel for making RPC calls.

    - **Raises**:
        - `ValueError`: If a secure channel is requested but the server address starts with `http://`.

    - **Description**:
        - This function creates and returns a gRPC asynchronous channel based on the provided server address and security flag.
        - It ensures that if `secure=True`, then the server address does not start with `http://`.
        - If the server address starts with `https://`, it will automatically switch to a secure connection even if `secure=False`.
    """
    if server_address.startswith("http://"):
        server_address = server_address.split("//")[1]
        if secure:
            raise ValueError("secure channel must use `https` or not use `http`")
    elif server_address.startswith("https://"):
        server_address = server_address.split("//")[1]
        if not secure:
            secure = True

    if secure:
        return grpc.aio.secure_channel(server_address, grpc.ssl_channel_credentials())
    else:
        return grpc.aio.insecure_channel(server_address)


class EconomyClient:
    """
    Client side of Economy service.

    - **Description**:
        - This class serves as a client interface to interact with the Economy Simulator via gRPC.
        - It establishes an asynchronous connection and provides methods to communicate with the service.
    """

    def __init__(
        self,
        server_address: str,
    ):
        """
        Initialize the EconomyClient.

        - **Args**:
            - `server_address` (`str`): The address of the Economy server to connect to.

        - **Attributes**:
            - `server_address` (`str`): The address of the Economy server.
            - `_aio_stub` (`OrgServiceStub`): A gRPC stub used to make remote calls to the Economy service.

        - **Description**:
            - Initializes the EconomyClient with the specified server address and security preference.
            - Creates an asynchronous gRPC channel using `_create_aio_channel`.
            - Instantiates a gRPC stub (`_aio_stub`) for interacting with the Economy service.
        """
        self.server_address = server_address

        secure = self.server_address.startswith("https")
        self.secure = secure
        aio_channel = _create_aio_channel(server_address, secure)
        self._aio_stub = org_grpc.OrgServiceStub(aio_channel)
        self._citizen_ids = set()
        self._firm_ids = set()
        self._bank_ids = set()
        self._nbs_ids = set()
        self._government_ids = set()
        self._log_list = []
        self._lock = asyncio.Lock()

    def get_log_list(self):
        return self._log_list

    def clear_log_list(self):
        self._log_list = []

    def __getstate__(self):
        """
        Copy the object's state from self.__dict__ which contains
        all our instance attributes. Always use the dict.copy()
        method to avoid modifying the original state.
        """
        state = self.__dict__.copy()
        # Remove the non-picklable entries.
        del state["_aio_stub"]
        return state

    def __setstate__(self, state):
        """
        Restore instance attributes (i.e., filename and mode) from the
        unpickled state dictionary.
        """
        self.__dict__.update(state)
        # Re-initialize the channel after unpickling
        aio_channel = _create_aio_channel(self.server_address, self.secure)
        self._aio_stub = org_grpc.OrgServiceStub(aio_channel)

    # TODO: remove the design
    def _get_request_type(self, id: Union[int, list[int]]) -> EconomyEntityType:
        if not isinstance(id, list):
            id = [id]
        if all(i in self._citizen_ids for i in id):
            return EconomyEntityType.Agent
        elif all(i in self._bank_ids for i in id):
            return EconomyEntityType.Bank
        elif all(i in self._nbs_ids for i in id):
            return EconomyEntityType.NBS
        elif all(i in self._government_ids for i in id):
            return EconomyEntityType.Government
        elif all(i in self._firm_ids for i in id):
            return EconomyEntityType.Firm
        else:
            raise ValueError(f"Invalid id {id}, this id does not exist!")

    async def get_ids(self):
        """
        Get the ids of agents and orgs
        """
        return (
            self._citizen_ids,
            self._bank_ids,
            self._nbs_ids,
            self._government_ids,
            self._firm_ids,
        )

    def set_ids(
        self,
        citizen_ids: set[int],
        firm_ids: set[int],
        bank_ids: set[int],
        nbs_ids: set[int],
        government_ids: set[int],
    ):
        """
        Set the ids of agents and orgs
        """
        self._citizen_ids = citizen_ids
        self._firm_ids = firm_ids
        self._bank_ids = bank_ids
        self._nbs_ids = nbs_ids
        self._government_ids = government_ids

    
    async def _get_agent(
        self, id: Union[list[int], int]
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        Get agent by id

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of the agent.

        - **Returns**:
            - `economyv2.Agent`: The agent object.
        """
        get_logger().debug(f"Getting agent {id}")
        if not isinstance(id, Sequence):
            id = [id]
        agents: org_service.GetAgentResponse = await self._aio_stub.GetAgent(
            org_service.GetAgentRequest(
                agent_ids=id,
            )
        )
        agent_dicts = MessageToDict(agents, preserving_proto_field_name=True)["agents"]
        if len(id) == 1:
            return agent_dicts[0]
        else:
            return agent_dicts

    
    async def _get_bank(
        self, id: Union[list[int], int]
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        Get bank by id

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of the bank.

        - **Returns**:
            - `economyv2.Bank`: The bank object.
        """
        get_logger().debug(f"Getting bank {id}")
        if isinstance(id, list):
            banks = []
            for bank_id in id:
                bank: org_service.GetBankResponse = await self._aio_stub.GetBank(
                    org_service.GetBankRequest(
                        bank_id=bank_id,
                    )
                )
                banks.append(bank)
            bank_dicts = [
                MessageToDict(bank.bank, preserving_proto_field_name=True)
                for bank in banks
            ]
            return bank_dicts
        else:
            bank: org_service.GetBankResponse = await self._aio_stub.GetBank(
                org_service.GetBankRequest(bank_id=id)
            )
            bank_dict = MessageToDict(bank.bank, preserving_proto_field_name=True)
            return bank_dict

    
    async def _get_firm(
        self, id: Union[list[int], int]
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        Get firm by id

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of the firm.

        - **Returns**:
            - `economyv2.Firm`: The firm object.
        """
        get_logger().debug(f"Getting firm {id}")
        if not isinstance(id, list):
            _id = [id]
        else:
            _id = id
        firms: org_service.GetFirmResponse = await self._aio_stub.GetFirm(
            org_service.GetFirmRequest(firm_ids=_id)
        )
        firm_dicts = MessageToDict(firms, preserving_proto_field_name=True)["firms"]
        if not isinstance(id, list):
            return firm_dicts[0]
        else:
            return firm_dicts

    
    async def _get_government(
        self, id: Union[list[int], int]
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        Get government by id

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of the government.

        - **Returns**:
            - `economyv2.Government`: The government object.
        """
        get_logger().debug(f"Getting government {id}")
        if isinstance(id, list):
            governments: list[org_service.GetGovernmentResponse] = [
                await self._aio_stub.GetGovernment(
                    org_service.GetGovernmentRequest(government_id=government_id)
                )
                for government_id in id
            ]
            government_dicts = [
                MessageToDict(government.government, preserving_proto_field_name=True)
                for government in governments
            ]
            return government_dicts
        else:
            government: org_service.GetGovernmentResponse = (
                await self._aio_stub.GetGovernment(
                    org_service.GetGovernmentRequest(government_id=id)
                )
            )
            government_dict = MessageToDict(
                government.government, preserving_proto_field_name=True
            )
            return government_dict

    
    async def _get_nbs(
        self, id: Union[list[int], int]
    ) -> Union[dict[str, Any], list[dict[str, Any]]]:
        """
        Get nbs by id

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of the nbs.

        - **Returns**:
            - `economyv2.Nbs`: The nbs object.
        """
        get_logger().debug(f"Getting NBS {id}")
        if isinstance(id, list):
            nbss: list[org_service.GetNBSResponse] = [
                await self._aio_stub.GetNBS(org_service.GetNBSRequest(nbs_id=nbs_id))
                for nbs_id in id
            ]
            nbs_dicts = [
                MessageToDict(nbs.nbs, preserving_proto_field_name=True) for nbs in nbss
            ]
            return nbs_dicts
        else:
            nbs: org_service.GetNBSResponse = await self._aio_stub.GetNBS(
                org_service.GetNBSRequest(nbs_id=id)
            )
            nbs_dict = MessageToDict(nbs.nbs, preserving_proto_field_name=True)
            return nbs_dict

    async def get(
        self,
        id: Union[list[int], int],
        key: Union[list[str], str],
    ) -> Any:
        """
        Get specific value

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of `Org` or `Agent`.
            - `key` (`str`): The attribute to fetch.

        - **Returns**:
            - Any
        """
        request_type = self._get_request_type(id)
        if request_type == EconomyEntityType.Agent:
            response = await self._get_agent(id)
        elif request_type == EconomyEntityType.Bank:
            response = await self._get_bank(id)
        elif request_type == EconomyEntityType.NBS:
            response = await self._get_nbs(id)
        elif request_type == EconomyEntityType.Government:
            response = await self._get_government(id)
        elif request_type == EconomyEntityType.Firm:
            response = await self._get_firm(id)
        else:
            raise ValueError(f"Invalid id {id}, this id does not exist!")
        if isinstance(id, Sequence):
            response = cast(list[dict[str, Any]], response)
            if isinstance(response, dict):
                response = [response]

            if not isinstance(key, list):
                results = [res[key] for res in response]
            else:
                results = []
                for k in key:
                    results.append([res[k] for res in response])
            return results
        else:
            get_logger().debug(f"response: {response}")
            res = cast(dict[str, Any], response)
            get_logger().debug(f"res: {res}")
            if isinstance(key, list):
                return [res[k] for k in key]
            else:
                return res[key]

    def _merge(self, original_dict: dict[str, Any], key: Any, value: Any) -> bool:
        try:
            orig_value = original_dict[key]
            _orig_type = type(orig_value)
            _new_type = type(value)
        except Exception:
            type_ = type(value)
            _orig_type = type_
            _new_type = type_
            orig_value = type_()
        if _orig_type != _new_type:
            get_logger().debug(
                f"Inconsistent type of original value {_orig_type.__name__} and to-update value {_new_type.__name__}"
            )
            return False
        else:
            if isinstance(orig_value, set):
                orig_value.update(set(value))
                original_dict[key] = orig_value
            elif isinstance(orig_value, dict):
                orig_value.update(dict(value))
                original_dict[key] = orig_value
            elif isinstance(orig_value, list):
                orig_value.extend(list(value))
                original_dict[key] = orig_value
            else:
                get_logger().warning(
                    f"Type of {type(orig_value)} does not support mode `merge`, using `replace` instead!"
                )
                return False
            return True

    async def update(
        self,
        id: Union[list[int], int],
        key: str,
        value: Union[Any, list[Any]],
        mode: Union[Literal["replace"], Literal["merge"]] = "replace",
    ) -> Any:
        """
        Update key-value pair

        - **Args**:
            - `id` (`Union[list[int], int]`): The id of `Org` or `Agent`.
            - `key` (`str`): The attribute to update.
            - `value` (`Union[Any, list[Any]]`): The value to update.
            - `mode` (Union[Literal["replace"], Literal["merge"]], optional): Update mode. Defaults to "replace".

        - **Returns**:
            - Any
        """
        if isinstance(id, list):
            if not isinstance(value, list):
                raise ValueError("Invalid value, the value must be a list!")
            if len(id) != len(value):
                raise ValueError(
                    "Invalid ids and values, the length of ids and values must be the same!"
                )
        else:
            id = [id]
            value = [value]
        request_type = self._get_request_type(id)
        if request_type == EconomyEntityType.Agent:
            original_dict = await self._get_agent(id)
        elif request_type == EconomyEntityType.Bank:
            original_dict = await self._get_bank(id)
        elif request_type == EconomyEntityType.NBS:
            original_dict = await self._get_nbs(id)
        elif request_type == EconomyEntityType.Government:
            original_dict = await self._get_government(id)
        elif request_type == EconomyEntityType.Firm:
            original_dict = await self._get_firm(id)
        else:
            raise ValueError(f"Invalid id {id}, this id does not exist!")
        if not isinstance(original_dict, list):
            original_dicts = [original_dict]
        else:
            original_dicts = original_dict
        if mode == "merge":
            for i in range(len(original_dicts)):
                if not self._merge(original_dicts[i], key, value[i]):
                    original_dicts[i][key] = value[i]
        else:
            for i in range(len(original_dicts)):
                original_dicts[i][key] = value[i]
        if request_type == EconomyEntityType.Agent:
            await self._aio_stub.UpdateAgent(
                org_service.UpdateAgentRequest(
                    agents=[economyv2.Agent(**v) for v in original_dicts]
                )
            )
        elif request_type == EconomyEntityType.Bank:
            for v in original_dicts:
                await self._aio_stub.UpdateBank(
                    org_service.UpdateBankRequest(bank=economyv2.Bank(**v))
                )
        elif request_type == EconomyEntityType.NBS:
            for v in original_dicts:
                await self._aio_stub.UpdateNBS(
                    org_service.UpdateNBSRequest(nbs=economyv2.NBS(**v))
                )
        elif request_type == EconomyEntityType.Government:
            for v in original_dicts:
                await self._aio_stub.UpdateGovernment(
                    org_service.UpdateGovernmentRequest(
                        government=economyv2.Government(**v)
                    )
                )
        elif request_type == EconomyEntityType.Firm:
            await self._aio_stub.UpdateFirm(
                org_service.UpdateFirmRequest(
                    firms=[economyv2.Firm(**v) for v in original_dicts]
                )
            )

    async def add_agents(self, configs: Union[list[dict], dict]):
        """
        Add one or more agents to the economy system.

        - **Args**:
            - `configs` (`Union[list[dict], dict]`): A single configuration dictionary or a list of dictionaries,
              each containing the necessary information to create an agent (e.g., id, currency).

        - **Returns**:
            - The method does not explicitly return any value but gathers the responses from adding each agent.

        - **Description**:
            - If a single configuration dictionary is provided, it is converted into a list.
            - For each configuration in the list, a task is created to asynchronously add an agent using the provided configuration.
            - All tasks are executed concurrently, and their results are gathered and returned.
        """
        if isinstance(configs, dict):
            configs = [configs]
        for config in configs:
            assert config["id"] in self._citizen_ids
            assert config.get("type", "Agent") == "Agent"
        tasks = [
            self._aio_stub.AddAgent(
                org_service.AddAgentRequest(
                    agents=[
                        economyv2.Agent(
                            id=config["id"],
                            currency=config.get("currency", 0.0),
                            skill=config.get("skill", 0.0),
                            consumption=config.get("consumption", 0.0),
                            income=config.get("income", 0.0),
                        )
                        for config in configs
                    ]
                )
            )
        ]
        await asyncio.gather(*tasks)

    async def add_orgs(self, configs: Union[list[dict], dict]):
        """
        Add one or more organizations to the economy system.

        - **Args**:
            - `configs` (`Union[List[Dict], Dict]`): A single configuration dictionary or a list of dictionaries,
              each containing the necessary information to create an organization (e.g., id, type, nominal_gdp, etc.).

        - **Returns**:
            - `List`: A list of responses from adding each organization.

        - **Raises**:
            - `KeyError`: If a required field is missing from the config dictionary.

        - **Description**:
            - Ensures `configs` is always a list, even if only one config is provided.
            - For each configuration in the list, creates a task to asynchronously add an organization using the provided configuration.
            - Executes all tasks concurrently and gathers their results.
        """
        if isinstance(configs, dict):
            configs = [configs]
        tasks = []
        for config in configs:
            org_type: str = config.get("type", None)
            if org_type == EconomyEntityType.Bank:
                assert config["id"] in self._bank_ids
                tasks.append(
                    self._aio_stub.AddBank(
                        org_service.AddBankRequest(
                            bank=economyv2.Bank(
                                id=config["id"],
                                citizen_ids=config.get("citizen_ids", []),
                                interest_rate=config.get("interest_rate", 0.0),
                                currency=config.get("currency", 0.0),
                            )
                        )
                    )
                )
            elif org_type == EconomyEntityType.Firm:
                assert config["id"] in self._firm_ids
                tasks.append(
                    self._aio_stub.AddFirm(
                        org_service.AddFirmRequest(
                            firms=[
                                economyv2.Firm(
                                    id=config["id"],
                                    employees=config.get("employees", []),
                                    price=config.get("price", 0),
                                    inventory=config.get("inventory", 0),
                                    demand=config.get("demand", 0),
                                    sales=config.get("sales", 0),
                                    currency=config.get("currency", 0.0),
                                )
                            ]
                        )
                    )
                )
            elif org_type == EconomyEntityType.Government:
                assert config["id"] in self._government_ids
                tasks.append(
                    self._aio_stub.AddGovernment(
                        org_service.AddGovernmentRequest(
                            government=economyv2.Government(
                                id=config["id"],
                                citizen_ids=config.get("citizen_ids", []),
                                bracket_cutoffs=config.get("bracket_cutoffs", []),
                                bracket_rates=config.get("bracket_rates", []),
                                currency=config.get("currency", 0.0),
                            )
                        )
                    )
                )
            elif org_type == EconomyEntityType.NBS:
                assert config["id"] in self._nbs_ids
                tasks.append(
                    self._aio_stub.AddNBS(
                        org_service.AddNBSRequest(
                            nbs=economyv2.NBS(
                                id=config["id"],
                                citizen_ids=config.get("citizen_ids", []),
                                nominal_gdp=config.get("nominal_gdp", {}),
                                real_gdp=config.get("real_gdp", {}),
                                unemployment=config.get("unemployment", {}),
                                wages=config.get("wages", {}),
                                prices=config.get("prices", {}),
                                working_hours=config.get("working_hours", {}),
                                depression=config.get("depression", {}),
                                consumption_currency=config.get(
                                    "consumption_currency", {}
                                ),
                                income_currency=config.get("income_currency", {}),
                                locus_control=config.get("locus_control", {}),
                                currency=config.get("currency", 0.0),
                            )
                        )
                    )
                )
            else:
                raise ValueError(f"Invalid org type {org_type}")
        await asyncio.gather(*tasks)

    async def calculate_taxes_due(
        self,
        org_id: int,
        agent_ids: list[int],
        incomes: list[float],
        enable_redistribution: bool,
    ):
        """
        Calculate the taxes due for agents based on their incomes.

        - **Args**:
            - `org_id` (`int`): The ID of the government organization.
            - `agent_ids` (`List[int]`): A list of IDs for the agents whose taxes are being calculated.
            - `incomes` (`List[float]`): A list of income values corresponding to each agent.
            - `enable_redistribution` (`bool`): Flag indicating whether redistribution is enabled.

        - **Returns**:
            - `Tuple[float, List[float]]`: A tuple containing the total taxes due and updated incomes after tax calculation.
        """
        request = org_service.CalculateTaxesDueRequest(
            government_id=org_id,
            agent_ids=agent_ids,
            incomes=incomes,
            enable_redistribution=enable_redistribution,
        )
        response: org_service.CalculateTaxesDueResponse = (
            await self._aio_stub.CalculateTaxesDue(request)
        )
        return (float(response.taxes_due), list(response.updated_incomes))

    async def calculate_consumption(
        self,
        org_ids: Union[int, list[int]],
        agent_id: int,
        demands: list[int],
        consumption_accumulation: bool = True,
    ):
        """
        Calculate consumption for agents based on their demands.

        - **Args**:
            - `org_ids` (`Union[int, list[int]]`): The ID of the firm providing goods or services.
            - `agent_id` (`int`): The ID of the agent whose consumption is being calculated.
            - `demands` (`List[int]`): A list of demand quantities corresponding to each agent.
            - `consumption_accumulation` (`bool`): Weather accumulation.

        - **Returns**:
            - `Tuple[int, List[float]]`: A tuple containing the remaining inventory and updated currencies for each agent.
        """
        if not isinstance(org_ids, Sequence):
            org_ids = [org_ids]
        request = org_service.CalculateConsumptionRequest(
            firm_ids=org_ids,
            agent_id=agent_id,
            demands=demands,
            consumption_accumulation=consumption_accumulation,
        )
        response: org_service.CalculateConsumptionResponse = (
            await self._aio_stub.CalculateConsumption(request)
        )
        if response.success:
            return response.actual_consumption
        else:
            return -1

    async def calculate_real_gdp(self, nbs_id: int):
        request = org_service.CalculateRealGDPRequest(nbs_id=nbs_id)
        response: org_service.CalculateRealGDPResponse = (
            await self._aio_stub.CalculateRealGDP(request)
        )
        return response.real_gdp

    async def calculate_interest(self, bank_id: int, agent_ids: list[int]):
        """
        Calculate interest for agents based on their accounts.

        - **Args**:
            - `bank_id` (`int`): The ID of the bank.
            - `agent_ids` (`List[int]`): A list of IDs for the agents whose interests are being calculated.

        - **Returns**:
            - `Tuple[float, List[float]]`: A tuple containing the total interest and updated currencies for each agent.
        """
        request = org_service.CalculateInterestRequest(
            bank_id=bank_id,
            agent_ids=agent_ids,
        )
        response: org_service.CalculateInterestResponse = (
            await self._aio_stub.CalculateInterest(request)
        )
        return (float(response.total_interest), list(response.updated_currencies))

    async def remove_agents(self, agent_ids: Union[int, list[int]]):
        """
        Remove one or more agents from the system.

        - **Args**:
            - `org_ids` (`Union[int, List[int]]`): A single ID or a list of IDs for the agents to be removed.
        """
        if isinstance(agent_ids, int):
            agent_ids = [agent_ids]
        tasks = [
            self._aio_stub.RemoveAgent(
                org_service.RemoveAgentRequest(agent_ids=agent_ids)
            )
        ]
        await asyncio.gather(*tasks)

    async def remove_banks(self, bank_ids: Union[int, list[int]]):
        """
        Remove one or more banks from the system.

        - **Args**:
            - `bank_ids` (`Union[int, List[int]]`): A single ID or a list of IDs for the banks to be removed.
        """
        if isinstance(bank_ids, int):
            bank_ids = [bank_ids]
        tasks = [
            self._aio_stub.RemoveBank(org_service.RemoveBankRequest(bank_id=bank_id))
            for bank_id in bank_ids
        ]
        await asyncio.gather(*tasks)

    async def remove_firms(self, firm_ids: Union[int, list[int]]):
        """
        Remove one or more firms from the system.

        - **Args**:
            - `firm_ids` (`Union[int, List[int]]`): A single ID or a list of IDs for the firms to be removed.
        """
        if isinstance(firm_ids, int):
            firm_ids = [firm_ids]
        tasks = [
            self._aio_stub.RemoveFirm(org_service.RemoveFirmRequest(firm_ids=firm_ids))
        ]
        await asyncio.gather(*tasks)

    async def remove_governments(self, government_ids: Union[int, list[int]]):
        """
        Remove one or more governments from the system.

        - **Args**:
            - `government_ids` (`Union[int, List[int]]`): A single ID or a list of IDs for the governments to be removed.
        """
        if isinstance(government_ids, int):
            government_ids = [government_ids]
        tasks = [
            self._aio_stub.RemoveGovernment(
                org_service.RemoveGovernmentRequest(government_id=government_id)
            )
            for government_id in government_ids
        ]
        await asyncio.gather(*tasks)

    async def remove_nbs(self, nbs_ids: Union[int, list[int]]):
        """
        Remove one or more nbs from the system.

        - **Args**:
            - `nbs_id` (`Union[int, List[int]]`): A single ID or a list of IDs for the NBS to be removed.
        """
        if isinstance(nbs_ids, int):
            nbs_ids = [nbs_ids]
        tasks = [
            self._aio_stub.RemoveNBS(org_service.RemoveNBSRequest(nbs_id=nbs_id))
            for nbs_id in nbs_ids
        ]
        await asyncio.gather(*tasks)

    async def save(
        self, file_path: str
    ) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
        """
        Save the current state of all economy entities to a specified file.

        - **Args**:
            - `file_path` (`str`): The path to the file where the economy entities will be saved.

        - **Returns**:
            - `Tuple[list[int], list[int], list[int], list[int], list[int]]`: A tuple containing lists of agent IDs and organization IDs that were saved.
        """
        request = org_service.SaveEconomyEntitiesRequest(
            file_path=file_path,
        )
        response: org_service.SaveEconomyEntitiesResponse = (
            await self._aio_stub.SaveEconomyEntities(request)
        )
        # current agent ids and org ids
        return (
            list(response.agent_ids),
            list(response.firm_ids),
            list(response.bank_ids),
            list(response.nbs_ids),
            list(response.government_ids),
        )

    async def load(self, file_path: str):
        """
        Load the state of economy entities from a specified file.

        - **Args**:
            - `file_path` (`str`): The path to the file from which the economy entities will be loaded.

        - **Returns**:
            - `Tuple[list[int], list[int], list[int], list[int], list[int]]`: A tuple containing lists of agent IDs and organization IDs that were loaded.
        """
        request = org_service.LoadEconomyEntitiesRequest(
            file_path=file_path,
        )
        response: org_service.LoadEconomyEntitiesResponse = (
            await self._aio_stub.LoadEconomyEntities(request)
        )
        # current agent ids and org ids
        return (
            list(response.agent_ids),
            list(response.firm_ids),
            list(response.bank_ids),
            list(response.nbs_ids),
            list(response.government_ids),
        )

    async def get_bank_ids(
        self,
    ) -> list[int]:
        """
        Get the IDs of bank entities.

        - **Returns**:
            - `List[int]`: A list of bank IDs.
        """
        request = org_service.ListBanksRequest()
        response: org_service.ListBanksResponse = await self._aio_stub.ListBanks(
            request
        )
        return [i.id for i in response.banks]

    async def get_nbs_ids(
        self,
    ) -> list[int]:
        """
        Get the IDs of NBS entities.

        - **Returns**:
            - `List[int]`: A list of NBS IDs.
        """
        request = org_service.ListNBSRequest()
        response: org_service.ListNBSResponse = await self._aio_stub.ListNBS(request)
        return [i.id for i in response.nbs_list]

    async def get_government_ids(
        self,
    ) -> list[int]:
        """
        Get the IDs of government entities.

        - **Returns**:
            - `List[int]`: A list of government IDs.
        """
        request = org_service.ListGovernmentsRequest()
        response: org_service.ListGovernmentsResponse = (
            await self._aio_stub.ListGovernments(request)
        )
        return [i.id for i in response.governments]

    async def get_firm_ids(
        self,
    ) -> list[int]:
        """
        Get the IDs of firm entities.

        - **Returns**:
            - `List[int]`: A list of firm IDs.
        """
        request = org_service.ListFirmsRequest()
        response: org_service.ListFirmsResponse = await self._aio_stub.ListFirms(
            request
        )
        return [i.id for i in response.firms]

    async def delta_update_bank(
        self,
        bank_id: int,
        delta_interest_rate: float = 0.0,
        delta_currency: float = 0.00,
        add_citizen_ids: list[int] = [],
        remove_citizen_ids: list[int] = [],
    ):
        """
        Incrementally update a bank's properties.

        - **Args**:
            - `bank_id` (`int`): The ID of the bank to update.
            - `delta_interest_rate` (`float`, optional): Change in interest rate, can be positive or negative. Defaults to 0.0.
            - `delta_currency` (`float`, optional): Change in currency amount, can be positive or negative. Defaults to 0.00.
            - `add_citizen_ids` (`list[int]`, optional): List of citizen IDs to add to the bank. Defaults to empty list.
            - `remove_citizen_ids` (`list[int]`, optional): List of citizen IDs to remove from the bank. Defaults to empty list.

        - **Returns**:
            This method does not return any value.

        - **Description**:
            - This method sends a request to the economy service via gRPC to incrementally update a bank's properties.
            - Can update interest rate, currency amount, and associated citizens simultaneously.
            - All parameters are optional except bank_id - only provide values for properties you want to change.
        """
        await self._aio_stub.DeltaUpdateBank(
            org_service.DeltaUpdateBankRequest(
                bank_id=bank_id,
                delta_interest_rate=delta_interest_rate,
                delta_currency=delta_currency,
                add_citizen_ids=add_citizen_ids,
                remove_citizen_ids=remove_citizen_ids,
            )
        )

    async def delta_update_nbs(
        self,
        nbs_id: int,
        delta_nominal_gdp: Optional[dict[str, float]] = None,
        delta_real_gdp: Optional[dict[str, float]] = None,
        delta_unemployment: Optional[dict[str, float]] = None,
        delta_wages: Optional[dict[str, float]] = None,
        delta_prices: Optional[dict[str, float]] = None,
        delta_working_hours: Optional[dict[str, float]] = None,
        delta_depression: Optional[dict[str, float]] = None,
        delta_consumption_currency: Optional[dict[str, float]] = None,
        delta_income_currency: Optional[dict[str, float]] = None,
        delta_locus_control: Optional[dict[str, float]] = None,
        delta_currency: float = 0.0,
        add_citizen_ids: Optional[list[int]] = None,
        remove_citizen_ids: Optional[list[int]] = None,
    ):
        """
        Incrementally update a National Bureau of Statistics (NBS) entity's properties.

        - **Args**:
            - `nbs_id` (`int`): The ID of the NBS entity to update.
            - `delta_nominal_gdp` (`dict[str,float]`): Changes to nominal GDP metrics by category.
            - `delta_real_gdp` (`dict[str,float]`): Changes to real GDP metrics by category.
            - `delta_unemployment` (`dict[str,float]`): Changes to unemployment metrics by category.
            - `delta_wages` (`dict[str,float]`): Changes to wage metrics by category.
            - `delta_prices` (`dict[str,float]`): Changes to price metrics by category.
            - `delta_working_hours` (`dict[str,float]`): Changes to working hours metrics by category.
            - `delta_depression` (`dict[str,float]`): Changes to depression metrics by category.
            - `delta_consumption_currency` (`dict[str,float]`): Changes to consumption currency metrics by category.
            - `delta_income_currency` (`dict[str,float]`): Changes to income currency metrics by category.
            - `delta_locus_control` (`dict[str,float]`): Changes to locus of control metrics by category.
            - `delta_currency` (`float`): Change in currency amount, can be positive or negative.
            - `add_citizen_ids` (`list[int]`): List of citizen IDs to add to the NBS entity.
            - `remove_citizen_ids` (`list[int]`): List of citizen IDs to remove from the NBS entity.

        - **Returns**:
            This method does not return any value.

        - **Description**:
            - This method sends a request to the economy service via gRPC to incrementally update an NBS entity's properties.
            - Each delta parameter represents changes to be applied to the corresponding statistic tracked by the NBS.
            - Dictionary parameters contain category-specific changes where keys are categories and values are the delta amounts.
            - Can update multiple statistical metrics and associated citizens simultaneously.
        """
        await self._aio_stub.DeltaUpdateNBS(
            org_service.DeltaUpdateNBSRequest(
                nbs_id=nbs_id,
                delta_nominal_gdp=delta_nominal_gdp,
                delta_real_gdp=delta_real_gdp,
                delta_unemployment=delta_unemployment,
                delta_wages=delta_wages,
                delta_prices=delta_prices,
                delta_working_hours=delta_working_hours,
                delta_depression=delta_depression,
                delta_consumption_currency=delta_consumption_currency,
                delta_income_currency=delta_income_currency,
                delta_locus_control=delta_locus_control,
                delta_currency=delta_currency,
                add_citizen_ids=add_citizen_ids,
                remove_citizen_ids=remove_citizen_ids,
            )
        )

    async def delta_update_government(
        self,
        government_id: int,
        delta_bracket_cutoffs: Optional[list[float]] = None,
        delta_bracket_rates: Optional[list[float]] = None,
        delta_currency: float = 0.0,
        add_citizen_ids: Optional[list[int]] = None,
        remove_citizen_ids: Optional[list[int]] = None,
    ):
        """
        Incrementally update a Government entity's properties.

        - **Args**:
            - `government_id` (`int`): The ID of the Government entity to update.
            - `delta_bracket_cutoffs` (`list[float]`): Changes to tax bracket cutoff values.
            - `delta_bracket_rates` (`list[float]`): Changes to tax bracket rate values.
            - `delta_currency` (`float`): Change in currency amount, can be positive or negative.
            - `add_citizen_ids` (`list[int]`): List of citizen IDs to add to the Government entity.
            - `remove_citizen_ids` (`list[int]`): List of citizen IDs to remove from the Government entity.

        - **Returns**:
            This method does not return any value.

        - **Description**:
            - This method sends a request to the economy service via gRPC to incrementally update a Government entity's properties.
            - Can update tax bracket information, currency amount, and associated citizens simultaneously.
            - The delta parameters represent changes to be applied to the corresponding values currently stored in the Government entity.
        """
        await self._aio_stub.DeltaUpdateGovernment(
            org_service.DeltaUpdateGovernmentRequest(
                government_id=government_id,
                delta_bracket_cutoffs=delta_bracket_cutoffs,
                delta_bracket_rates=delta_bracket_rates,
                delta_currency=delta_currency,
                add_citizen_ids=add_citizen_ids,
                remove_citizen_ids=remove_citizen_ids,
            )
        )

    async def delta_update_firms(
        self,
        firm_id: Union[int, list[int]],
        delta_price: Optional[Union[float, list[float]]] = None,
        delta_inventory: Optional[Union[int, list[int]]] = None,
        delta_demand: Optional[Union[float, list[float]]] = None,
        delta_sales: Optional[Union[float, list[float]]] = None,
        delta_currency: Optional[Union[float, list[float]]] = None,
        add_employee_ids: Optional[Union[list[int], list[list[int]]]] = None,
        remove_employee_ids: Optional[Union[list[int], list[list[int]]]] = None,
    ):
        """
        Incrementally update one or more firms' properties.

        Args:
            firm_id: Single firm ID or list of firm IDs
            delta_price: Change in price(s)
            delta_inventory: Change in inventory level(s)
            delta_demand: Change in demand level(s)
            delta_sales: Change in sales amount(s)
            delta_currency: Change in currency amount(s)
            add_employee_ids: Employee IDs to add (single list or list of lists)
            remove_employee_ids: Employee IDs to remove (single list or list of lists)
        """
        # Convert single firm_id to list for uniform processing
        firm_ids = [firm_id] if isinstance(firm_id, int) else firm_id

        # Prepare parameter lists with proper length
        def prepare_param(param: Any, param_name: str) -> list[Any]:
            if param is None:
                return [None] * len(firm_ids)
            if not isinstance(param, list):
                return [param] * len(firm_ids)
            if len(param) != len(firm_ids):
                raise ValueError(
                    f"Length of {param_name} ({len(param)}) must match length of firm_ids ({len(firm_ids)})"
                )
            return param

        # Prepare all parameters
        delta_prices = prepare_param(delta_price, "delta_price")
        delta_inventories = prepare_param(delta_inventory, "delta_inventory")
        delta_demands = prepare_param(delta_demand, "delta_demand")
        delta_sales_list = prepare_param(delta_sales, "delta_sales")
        delta_currencies = prepare_param(delta_currency, "delta_currency")
        add_employee_ids_list = prepare_param(add_employee_ids, "add_employee_ids")
        remove_employee_ids_list = prepare_param(
            remove_employee_ids, "remove_employee_ids"
        )

        # Create updates list
        updates = []
        for i in range(len(firm_ids)):
            update = org_service.FirmDeltaUpdate(
                firm_id=firm_ids[i],
                delta_price=delta_prices[i],
                delta_inventory=delta_inventories[i],
                delta_demand=delta_demands[i],
                delta_sales=delta_sales_list[i],
                delta_currency=delta_currencies[i],
                add_employees=add_employee_ids_list[i],
                remove_employees=remove_employee_ids_list[i],
            )
            updates.append(update)

        # Send request
        await self._aio_stub.DeltaUpdateFirm(
            org_service.DeltaUpdateFirmRequest(updates=updates)
        )

    async def delta_update_agents(
        self,
        agent_id: Union[int, list[int]],
        new_firm_id: Optional[Union[int, list[int]]] = None,
        delta_currency: Optional[Union[float, list[float]]] = None,
        delta_skill: Optional[Union[float, list[float]]] = None,
        delta_consumption: Optional[Union[float, list[float]]] = None,
        delta_income: Optional[Union[float, list[float]]] = None,
    ):
        """Update agent attributes with delta values."""
        # Convert single values to lists for uniform processing
        agent_ids = [agent_id] if not isinstance(agent_id, list) else agent_id

        # Handle each parameter consistently
        new_firm_ids = self._prepare_parameter(new_firm_id, len(agent_ids))
        delta_currencies = self._prepare_parameter(delta_currency, len(agent_ids))
        delta_skills = self._prepare_parameter(delta_skill, len(agent_ids))
        delta_consumptions = self._prepare_parameter(delta_consumption, len(agent_ids))
        delta_incomes = self._prepare_parameter(delta_income, len(agent_ids))

        # Validate all lists have the same length
        param_lengths = [
            len(agent_ids),
            len(delta_currencies),
            len(delta_skills),
            len(delta_consumptions),
            len(delta_incomes),
        ]

        if len(set(param_lengths)) > 1:
            raise ValueError(
                "Invalid input, the length of agent_id, delta_currency, delta_skill, "
                "delta_consumption, delta_income must be the same!"
            )

        # Create updates list
        updates = [
            org_service.AgentDeltaUpdate(
                agent_id=agent_ids[i],
                new_firm_id=new_firm_ids[i],
                delta_currency=delta_currencies[i],
                delta_skill=delta_skills[i],
                delta_consumption=delta_consumptions[i],
                delta_income=delta_incomes[i],
            )
            for i in range(len(agent_ids))
        ]

        # Send request
        await self._aio_stub.DeltaUpdateAgent(
            org_service.DeltaUpdateAgentRequest(updates=updates)
        )

    def _prepare_parameter(self, param: Any, length: int) -> list[Any]:
        """Helper method to prepare parameters for batch processing."""
        if param is None:
            return [None] * length
        elif not isinstance(param, list):
            return [param] * length
        return param
