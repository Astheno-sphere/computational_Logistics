# {py:mod}`agentsociety.agent.agent`

```{py:module} agentsociety.agent.agent
```

```{autodoc2-docstring} agentsociety.agent.agent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`CitizenAgentBase <agentsociety.agent.agent.CitizenAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase
    :summary:
    ```
* - {py:obj}`InstitutionAgentBase <agentsociety.agent.agent.InstitutionAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase
    :summary:
    ```
* - {py:obj}`FirmAgentBase <agentsociety.agent.agent.FirmAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.FirmAgentBase
    :summary:
    ```
* - {py:obj}`BankAgentBase <agentsociety.agent.agent.BankAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.BankAgentBase
    :summary:
    ```
* - {py:obj}`NBSAgentBase <agentsociety.agent.agent.NBSAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.NBSAgentBase
    :summary:
    ```
* - {py:obj}`GovernmentAgentBase <agentsociety.agent.agent.GovernmentAgentBase>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.GovernmentAgentBase
    :summary:
    ```
* - {py:obj}`SupervisorBase <agentsociety.agent.agent.SupervisorBase>`
  -
* - {py:obj}`IndividualAgentBase <agentsociety.agent.agent.IndividualAgentBase>`
  -
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.agent.agent.__all__>`
  - ```{autodoc2-docstring} agentsociety.agent.agent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.agent.agent.__all__
:value: >
   ['CitizenAgentBase', 'FirmAgentBase', 'BankAgentBase', 'NBSAgentBase', 'GovernmentAgentBase', 'Super...

```{autodoc2-docstring} agentsociety.agent.agent.__all__
```

````

`````{py:class} CitizenAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.CitizenAgentBase

Bases: {py:obj}`agentsociety.agent.agent_base.Agent`

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.__init__
```

````{py:method} init()
:canonical: agentsociety.agent.agent.CitizenAgentBase.init
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.init
```

````

````{py:method} _bind_to_simulator()
:canonical: agentsociety.agent.agent.CitizenAgentBase._bind_to_simulator
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase._bind_to_simulator
```

````

````{py:method} _bind_to_economy()
:canonical: agentsociety.agent.agent.CitizenAgentBase._bind_to_economy
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase._bind_to_economy
```

````

````{py:method} update_motion()
:canonical: agentsociety.agent.agent.CitizenAgentBase.update_motion
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.update_motion
```

````

````{py:method} do_survey(survey: agentsociety.survey.models.Survey) -> str
:canonical: agentsociety.agent.agent.CitizenAgentBase.do_survey
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.do_survey
```

````

````{py:method} _handle_survey_with_storage(survey: agentsociety.survey.models.Survey, survey_day: typing.Optional[int] = None, survey_t: typing.Optional[float] = None, is_pending_survey: bool = False, pending_survey_id: typing.Optional[int] = None) -> str
:canonical: agentsociety.agent.agent.CitizenAgentBase._handle_survey_with_storage
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase._handle_survey_with_storage
```

````

````{py:method} do_interview(question: str) -> str
:canonical: agentsociety.agent.agent.CitizenAgentBase.do_interview
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.do_interview
```

````

````{py:method} _handle_interview_with_storage(message: agentsociety.message.Message) -> str
:canonical: agentsociety.agent.agent.CitizenAgentBase._handle_interview_with_storage
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase._handle_interview_with_storage
```

````

````{py:method} save_agent_thought(thought: str)
:canonical: agentsociety.agent.agent.CitizenAgentBase.save_agent_thought
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.save_agent_thought
```

````

````{py:method} do_chat(message: agentsociety.message.Message) -> str
:canonical: agentsociety.agent.agent.CitizenAgentBase.do_chat
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.do_chat
```

````

````{py:method} _handle_agent_chat_with_storage(message: agentsociety.message.Message)
:canonical: agentsociety.agent.agent.CitizenAgentBase._handle_agent_chat_with_storage
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase._handle_agent_chat_with_storage
```

````

````{py:method} get_aoi_info()
:canonical: agentsociety.agent.agent.CitizenAgentBase.get_aoi_info
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.get_aoi_info
```

````

````{py:method} get_nowtime()
:canonical: agentsociety.agent.agent.CitizenAgentBase.get_nowtime
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.get_nowtime
```

````

````{py:method} before_forward()
:canonical: agentsociety.agent.agent.CitizenAgentBase.before_forward
:async:

```{autodoc2-docstring} agentsociety.agent.agent.CitizenAgentBase.before_forward
```

````

`````

`````{py:class} InstitutionAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.InstitutionAgentBase

Bases: {py:obj}`agentsociety.agent.agent_base.Agent`

```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase.__init__
```

````{py:method} init()
:canonical: agentsociety.agent.agent.InstitutionAgentBase.init
:async:

```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase.init
```

````

````{py:method} _bind_to_economy()
:canonical: agentsociety.agent.agent.InstitutionAgentBase._bind_to_economy
:async:

```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase._bind_to_economy
```

````

````{py:method} react_to_intervention(intervention_message: str)
:canonical: agentsociety.agent.agent.InstitutionAgentBase.react_to_intervention
:async:

```{autodoc2-docstring} agentsociety.agent.agent.InstitutionAgentBase.react_to_intervention
```

````

`````

````{py:class} FirmAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.FirmAgentBase

Bases: {py:obj}`agentsociety.agent.agent.InstitutionAgentBase`

```{autodoc2-docstring} agentsociety.agent.agent.FirmAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.FirmAgentBase.__init__
```

````

````{py:class} BankAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.BankAgentBase

Bases: {py:obj}`agentsociety.agent.agent.InstitutionAgentBase`

```{autodoc2-docstring} agentsociety.agent.agent.BankAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.BankAgentBase.__init__
```

````

````{py:class} NBSAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.NBSAgentBase

Bases: {py:obj}`agentsociety.agent.agent.InstitutionAgentBase`

```{autodoc2-docstring} agentsociety.agent.agent.NBSAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.NBSAgentBase.__init__
```

````

````{py:class} GovernmentAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.GovernmentAgentBase

Bases: {py:obj}`agentsociety.agent.agent.InstitutionAgentBase`

```{autodoc2-docstring} agentsociety.agent.agent.GovernmentAgentBase
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent.GovernmentAgentBase.__init__
```

````

`````{py:class} SupervisorBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.SupervisorBase

Bases: {py:obj}`agentsociety.agent.agent_base.Agent`

````{py:method} forward(current_round_messages: list[agentsociety.message.Message]) -> tuple[dict[agentsociety.message.Message, bool], list[agentsociety.message.Message]]
:canonical: agentsociety.agent.agent.SupervisorBase.forward
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.agent.SupervisorBase.forward
```

````

`````

`````{py:class} IndividualAgentBase(id: int, name: str, toolbox: agentsociety.agent.agent_base.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent.IndividualAgentBase

Bases: {py:obj}`agentsociety.agent.agent_base.Agent`

````{py:method} run(task: agentsociety.taskloader.Task) -> typing.Any
:canonical: agentsociety.agent.agent.IndividualAgentBase.run
:async:

```{autodoc2-docstring} agentsociety.agent.agent.IndividualAgentBase.run
```

````

````{py:method} forward(task_context: dict[str, typing.Any]) -> typing.Any
:canonical: agentsociety.agent.agent.IndividualAgentBase.forward
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.agent.IndividualAgentBase.forward
```

````

`````
