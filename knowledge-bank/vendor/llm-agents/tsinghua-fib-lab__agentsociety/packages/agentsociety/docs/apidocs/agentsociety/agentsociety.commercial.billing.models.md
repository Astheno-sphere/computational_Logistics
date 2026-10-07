# {py:mod}`agentsociety.commercial.billing.models`

```{py:module} agentsociety.commercial.billing.models
```

```{autodoc2-docstring} agentsociety.commercial.billing.models
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ItemEnum <agentsociety.commercial.billing.models.ItemEnum>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum
    :summary:
    ```
* - {py:obj}`Account <agentsociety.commercial.billing.models.Account>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.Account
    :summary:
    ```
* - {py:obj}`ExperimentBillConfig <agentsociety.commercial.billing.models.ExperimentBillConfig>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig
    :summary:
    ```
* - {py:obj}`Bill <agentsociety.commercial.billing.models.Bill>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill
    :summary:
    ```
* - {py:obj}`ApiAccount <agentsociety.commercial.billing.models.ApiAccount>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount
    :summary:
    ```
* - {py:obj}`ApiBill <agentsociety.commercial.billing.models.ApiBill>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.commercial.billing.models.__all__>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.models.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.commercial.billing.models.__all__
:value: >
   ['Bill', 'ApiBill', 'Account', 'ApiAccount', 'ItemEnum']

```{autodoc2-docstring} agentsociety.commercial.billing.models.__all__
```

````

`````{py:class} ItemEnum()
:canonical: agentsociety.commercial.billing.models.ItemEnum

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum.__init__
```

````{py:attribute} RECHARGE
:canonical: agentsociety.commercial.billing.models.ItemEnum.RECHARGE
:value: >
   'recharge'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum.RECHARGE
```

````

````{py:attribute} LLM_INPUT_TOKEN
:canonical: agentsociety.commercial.billing.models.ItemEnum.LLM_INPUT_TOKEN
:value: >
   'llm_input_token'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum.LLM_INPUT_TOKEN
```

````

````{py:attribute} LLM_OUTPUT_TOKEN
:canonical: agentsociety.commercial.billing.models.ItemEnum.LLM_OUTPUT_TOKEN
:value: >
   'llm_output_token'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum.LLM_OUTPUT_TOKEN
```

````

````{py:attribute} RUNTIME
:canonical: agentsociety.commercial.billing.models.ItemEnum.RUNTIME
:value: >
   'run_time'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ItemEnum.RUNTIME
```

````

`````

`````{py:class} Account
:canonical: agentsociety.commercial.billing.models.Account

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account
```

````{py:attribute} __tablename__
:canonical: agentsociety.commercial.billing.models.Account.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.commercial.billing.models.Account.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account.tenant_id
```

````

````{py:attribute} balance
:canonical: agentsociety.commercial.billing.models.Account.balance
:type: sqlalchemy.orm.Mapped[agentsociety.webapi.models._base.MoneyDecimal]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account.balance
```

````

````{py:attribute} created_at
:canonical: agentsociety.commercial.billing.models.Account.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.commercial.billing.models.Account.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Account.updated_at
```

````

`````

`````{py:class} ExperimentBillConfig
:canonical: agentsociety.commercial.billing.models.ExperimentBillConfig

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig
```

````{py:attribute} __tablename__
:canonical: agentsociety.commercial.billing.models.ExperimentBillConfig.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.commercial.billing.models.ExperimentBillConfig.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig.tenant_id
```

````

````{py:attribute} exp_id
:canonical: agentsociety.commercial.billing.models.ExperimentBillConfig.exp_id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig.exp_id
```

````

````{py:attribute} llm_config_id
:canonical: agentsociety.commercial.billing.models.ExperimentBillConfig.llm_config_id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.ExperimentBillConfig.llm_config_id
```

````

`````

`````{py:class} Bill
:canonical: agentsociety.commercial.billing.models.Bill

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill
```

````{py:attribute} __tablename__
:canonical: agentsociety.commercial.billing.models.Bill.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.commercial.billing.models.Bill.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.commercial.billing.models.Bill.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.id
```

````

````{py:attribute} related_exp_id
:canonical: agentsociety.commercial.billing.models.Bill.related_exp_id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.related_exp_id
```

````

````{py:attribute} item
:canonical: agentsociety.commercial.billing.models.Bill.item
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.item
```

````

````{py:attribute} amount
:canonical: agentsociety.commercial.billing.models.Bill.amount
:type: sqlalchemy.orm.Mapped[agentsociety.webapi.models._base.MoneyDecimal]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.amount
```

````

````{py:attribute} unit_price
:canonical: agentsociety.commercial.billing.models.Bill.unit_price
:type: sqlalchemy.orm.Mapped[agentsociety.webapi.models._base.MoneyDecimal]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.unit_price
```

````

````{py:attribute} quantity
:canonical: agentsociety.commercial.billing.models.Bill.quantity
:type: sqlalchemy.orm.Mapped[float]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.quantity
```

````

````{py:attribute} description
:canonical: agentsociety.commercial.billing.models.Bill.description
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.description
```

````

````{py:attribute} created_at
:canonical: agentsociety.commercial.billing.models.Bill.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.created_at
```

````

````{py:attribute} __table_args__
:canonical: agentsociety.commercial.billing.models.Bill.__table_args__
:value: >
   ()

```{autodoc2-docstring} agentsociety.commercial.billing.models.Bill.__table_args__
```

````

`````

``````{py:class} ApiAccount(/, **data: typing.Any)
:canonical: agentsociety.commercial.billing.models.ApiAccount

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.__init__
```

````{py:attribute} balance
:canonical: agentsociety.commercial.billing.models.ApiAccount.balance
:type: decimal.Decimal
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.balance
```

````

````{py:attribute} created_at
:canonical: agentsociety.commercial.billing.models.ApiAccount.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.commercial.billing.models.ApiAccount.updated_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.commercial.billing.models.ApiAccount.Config

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.commercial.billing.models.ApiAccount.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiAccount.Config.from_attributes
```

````

`````

``````

``````{py:class} ApiBill(/, **data: typing.Any)
:canonical: agentsociety.commercial.billing.models.ApiBill

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.__init__
```

````{py:attribute} id
:canonical: agentsociety.commercial.billing.models.ApiBill.id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.id
```

````

````{py:attribute} related_exp_id
:canonical: agentsociety.commercial.billing.models.ApiBill.related_exp_id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.related_exp_id
```

````

````{py:attribute} item
:canonical: agentsociety.commercial.billing.models.ApiBill.item
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.item
```

````

````{py:attribute} amount
:canonical: agentsociety.commercial.billing.models.ApiBill.amount
:type: decimal.Decimal
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.amount
```

````

````{py:attribute} unit_price
:canonical: agentsociety.commercial.billing.models.ApiBill.unit_price
:type: decimal.Decimal
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.unit_price
```

````

````{py:attribute} quantity
:canonical: agentsociety.commercial.billing.models.ApiBill.quantity
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.quantity
```

````

````{py:attribute} description
:canonical: agentsociety.commercial.billing.models.ApiBill.description
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.description
```

````

````{py:attribute} created_at
:canonical: agentsociety.commercial.billing.models.ApiBill.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.created_at
```

````

`````{py:class} Config
:canonical: agentsociety.commercial.billing.models.ApiBill.Config

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.commercial.billing.models.ApiBill.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.commercial.billing.models.ApiBill.Config.from_attributes
```

````

`````

``````
