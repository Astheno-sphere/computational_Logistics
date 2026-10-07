# {py:mod}`agentsociety.commercial.billing.calculator`

```{py:module} agentsociety.commercial.billing.calculator
```

```{autodoc2-docstring} agentsociety.commercial.billing.calculator
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`compute_bill <agentsociety.commercial.billing.calculator.compute_bill>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.calculator.compute_bill
    :summary:
    ```
* - {py:obj}`check_balance <agentsociety.commercial.billing.calculator.check_balance>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.calculator.check_balance
    :summary:
    ```
* - {py:obj}`record_experiment_bill <agentsociety.commercial.billing.calculator.record_experiment_bill>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.calculator.record_experiment_bill
    :summary:
    ```
````

### API

````{py:function} compute_bill(db: sqlalchemy.ext.asyncio.AsyncSession, experiment, rates: typing.Optional[typing.Dict[str, float]] = None) -> None
:canonical: agentsociety.commercial.billing.calculator.compute_bill
:async:

```{autodoc2-docstring} agentsociety.commercial.billing.calculator.compute_bill
```
````

````{py:function} check_balance(tenant_id: str, db: sqlalchemy.ext.asyncio.AsyncSession) -> bool
:canonical: agentsociety.commercial.billing.calculator.check_balance
:async:

```{autodoc2-docstring} agentsociety.commercial.billing.calculator.check_balance
```
````

````{py:function} record_experiment_bill(db: sqlalchemy.ext.asyncio.AsyncSession, tenant_id: str, exp_id: uuid.UUID, llm_config_id: typing.Optional[uuid.UUID] = None) -> None
:canonical: agentsociety.commercial.billing.calculator.record_experiment_bill
:async:

```{autodoc2-docstring} agentsociety.commercial.billing.calculator.record_experiment_bill
```
````
