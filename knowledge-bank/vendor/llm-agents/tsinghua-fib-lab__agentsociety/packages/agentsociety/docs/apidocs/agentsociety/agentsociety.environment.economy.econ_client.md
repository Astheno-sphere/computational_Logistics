# {py:mod}`agentsociety.environment.economy.econ_client`

```{py:module} agentsociety.environment.economy.econ_client
```

```{autodoc2-docstring} agentsociety.environment.economy.econ_client
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`EconomyEntityType <agentsociety.environment.economy.econ_client.EconomyEntityType>`
  -
* - {py:obj}`EconomyClient <agentsociety.environment.economy.econ_client.EconomyClient>`
  - ```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_create_aio_channel <agentsociety.environment.economy.econ_client._create_aio_channel>`
  - ```{autodoc2-docstring} agentsociety.environment.economy.econ_client._create_aio_channel
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.environment.economy.econ_client.__all__>`
  - ```{autodoc2-docstring} agentsociety.environment.economy.econ_client.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.environment.economy.econ_client.__all__
:value: >
   ['EconomyClient']

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.__all__
```

````

`````{py:class} EconomyEntityType()
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType

Bases: {py:obj}`int`, {py:obj}`enum.Enum`

````{py:attribute} Unspecified
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.Unspecified
:value: >
   0

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.Unspecified
```

````

````{py:attribute} Agent
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.Agent
:value: >
   1

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.Agent
```

````

````{py:attribute} Bank
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.Bank
:value: >
   2

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.Bank
```

````

````{py:attribute} Firm
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.Firm
:value: >
   3

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.Firm
```

````

````{py:attribute} Government
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.Government
:value: >
   4

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.Government
```

````

````{py:attribute} NBS
:canonical: agentsociety.environment.economy.econ_client.EconomyEntityType.NBS
:value: >
   5

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyEntityType.NBS
```

````

`````

````{py:function} _create_aio_channel(server_address: str, secure: bool = False) -> grpc.aio.Channel
:canonical: agentsociety.environment.economy.econ_client._create_aio_channel

```{autodoc2-docstring} agentsociety.environment.economy.econ_client._create_aio_channel
```
````

`````{py:class} EconomyClient(server_address: str)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.__init__
```

````{py:method} get_log_list()
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_log_list

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_log_list
```

````

````{py:method} clear_log_list()
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.clear_log_list

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.clear_log_list
```

````

````{py:method} __getstate__()
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.__getstate__

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.__getstate__
```

````

````{py:method} __setstate__(state)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.__setstate__

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.__setstate__
```

````

````{py:method} _get_request_type(id: typing.Union[int, list[int]]) -> agentsociety.environment.economy.econ_client.EconomyEntityType
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_request_type

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_request_type
```

````

````{py:method} get_ids()
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_ids
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_ids
```

````

````{py:method} set_ids(citizen_ids: set[int], firm_ids: set[int], bank_ids: set[int], nbs_ids: set[int], government_ids: set[int])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.set_ids

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.set_ids
```

````

````{py:method} _get_agent(id: typing.Union[list[int], int]) -> typing.Union[dict[str, typing.Any], list[dict[str, typing.Any]]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_agent
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_agent
```

````

````{py:method} _get_bank(id: typing.Union[list[int], int]) -> typing.Union[dict[str, typing.Any], list[dict[str, typing.Any]]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_bank
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_bank
```

````

````{py:method} _get_firm(id: typing.Union[list[int], int]) -> typing.Union[dict[str, typing.Any], list[dict[str, typing.Any]]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_firm
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_firm
```

````

````{py:method} _get_government(id: typing.Union[list[int], int]) -> typing.Union[dict[str, typing.Any], list[dict[str, typing.Any]]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_government
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_government
```

````

````{py:method} _get_nbs(id: typing.Union[list[int], int]) -> typing.Union[dict[str, typing.Any], list[dict[str, typing.Any]]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._get_nbs
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._get_nbs
```

````

````{py:method} get(id: typing.Union[list[int], int], key: typing.Union[list[str], str]) -> typing.Any
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get
```

````

````{py:method} _merge(original_dict: dict[str, typing.Any], key: typing.Any, value: typing.Any) -> bool
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._merge

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._merge
```

````

````{py:method} update(id: typing.Union[list[int], int], key: str, value: typing.Union[typing.Any, list[typing.Any]], mode: typing.Union[typing.Literal[replace], typing.Literal[merge]] = 'replace') -> typing.Any
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.update
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.update
```

````

````{py:method} add_agents(configs: typing.Union[list[dict], dict])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.add_agents
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.add_agents
```

````

````{py:method} add_orgs(configs: typing.Union[list[dict], dict])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.add_orgs
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.add_orgs
```

````

````{py:method} calculate_taxes_due(org_id: int, agent_ids: list[int], incomes: list[float], enable_redistribution: bool)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.calculate_taxes_due
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.calculate_taxes_due
```

````

````{py:method} calculate_consumption(org_ids: typing.Union[int, list[int]], agent_id: int, demands: list[int], consumption_accumulation: bool = True)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.calculate_consumption
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.calculate_consumption
```

````

````{py:method} calculate_real_gdp(nbs_id: int)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.calculate_real_gdp
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.calculate_real_gdp
```

````

````{py:method} calculate_interest(bank_id: int, agent_ids: list[int])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.calculate_interest
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.calculate_interest
```

````

````{py:method} remove_agents(agent_ids: typing.Union[int, list[int]])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.remove_agents
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.remove_agents
```

````

````{py:method} remove_banks(bank_ids: typing.Union[int, list[int]])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.remove_banks
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.remove_banks
```

````

````{py:method} remove_firms(firm_ids: typing.Union[int, list[int]])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.remove_firms
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.remove_firms
```

````

````{py:method} remove_governments(government_ids: typing.Union[int, list[int]])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.remove_governments
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.remove_governments
```

````

````{py:method} remove_nbs(nbs_ids: typing.Union[int, list[int]])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.remove_nbs
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.remove_nbs
```

````

````{py:method} save(file_path: str) -> tuple[list[int], list[int], list[int], list[int], list[int]]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.save
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.save
```

````

````{py:method} load(file_path: str)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.load
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.load
```

````

````{py:method} get_bank_ids() -> list[int]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_bank_ids
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_bank_ids
```

````

````{py:method} get_nbs_ids() -> list[int]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_nbs_ids
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_nbs_ids
```

````

````{py:method} get_government_ids() -> list[int]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_government_ids
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_government_ids
```

````

````{py:method} get_firm_ids() -> list[int]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.get_firm_ids
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.get_firm_ids
```

````

````{py:method} delta_update_bank(bank_id: int, delta_interest_rate: float = 0.0, delta_currency: float = 0.0, add_citizen_ids: list[int] = [], remove_citizen_ids: list[int] = [])
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.delta_update_bank
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.delta_update_bank
```

````

````{py:method} delta_update_nbs(nbs_id: int, delta_nominal_gdp: typing.Optional[dict[str, float]] = None, delta_real_gdp: typing.Optional[dict[str, float]] = None, delta_unemployment: typing.Optional[dict[str, float]] = None, delta_wages: typing.Optional[dict[str, float]] = None, delta_prices: typing.Optional[dict[str, float]] = None, delta_working_hours: typing.Optional[dict[str, float]] = None, delta_depression: typing.Optional[dict[str, float]] = None, delta_consumption_currency: typing.Optional[dict[str, float]] = None, delta_income_currency: typing.Optional[dict[str, float]] = None, delta_locus_control: typing.Optional[dict[str, float]] = None, delta_currency: float = 0.0, add_citizen_ids: typing.Optional[list[int]] = None, remove_citizen_ids: typing.Optional[list[int]] = None)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.delta_update_nbs
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.delta_update_nbs
```

````

````{py:method} delta_update_government(government_id: int, delta_bracket_cutoffs: typing.Optional[list[float]] = None, delta_bracket_rates: typing.Optional[list[float]] = None, delta_currency: float = 0.0, add_citizen_ids: typing.Optional[list[int]] = None, remove_citizen_ids: typing.Optional[list[int]] = None)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.delta_update_government
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.delta_update_government
```

````

````{py:method} delta_update_firms(firm_id: typing.Union[int, list[int]], delta_price: typing.Optional[typing.Union[float, list[float]]] = None, delta_inventory: typing.Optional[typing.Union[int, list[int]]] = None, delta_demand: typing.Optional[typing.Union[float, list[float]]] = None, delta_sales: typing.Optional[typing.Union[float, list[float]]] = None, delta_currency: typing.Optional[typing.Union[float, list[float]]] = None, add_employee_ids: typing.Optional[typing.Union[list[int], list[list[int]]]] = None, remove_employee_ids: typing.Optional[typing.Union[list[int], list[list[int]]]] = None)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.delta_update_firms
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.delta_update_firms
```

````

````{py:method} delta_update_agents(agent_id: typing.Union[int, list[int]], new_firm_id: typing.Optional[typing.Union[int, list[int]]] = None, delta_currency: typing.Optional[typing.Union[float, list[float]]] = None, delta_skill: typing.Optional[typing.Union[float, list[float]]] = None, delta_consumption: typing.Optional[typing.Union[float, list[float]]] = None, delta_income: typing.Optional[typing.Union[float, list[float]]] = None)
:canonical: agentsociety.environment.economy.econ_client.EconomyClient.delta_update_agents
:async:

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient.delta_update_agents
```

````

````{py:method} _prepare_parameter(param: typing.Any, length: int) -> list[typing.Any]
:canonical: agentsociety.environment.economy.econ_client.EconomyClient._prepare_parameter

```{autodoc2-docstring} agentsociety.environment.economy.econ_client.EconomyClient._prepare_parameter
```

````

`````
