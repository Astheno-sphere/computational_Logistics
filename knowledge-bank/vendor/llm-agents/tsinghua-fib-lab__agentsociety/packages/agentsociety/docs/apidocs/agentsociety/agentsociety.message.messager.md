# {py:mod}`agentsociety.message.messager`

```{py:module} agentsociety.message.messager
```

```{autodoc2-docstring} agentsociety.message.messager
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`MessageKind <agentsociety.message.messager.MessageKind>`
  -
* - {py:obj}`Message <agentsociety.message.messager.Message>`
  -
* - {py:obj}`Messager <agentsociety.message.messager.Messager>`
  - ```{autodoc2-docstring} agentsociety.message.messager.Messager
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.message.messager.__all__>`
  - ```{autodoc2-docstring} agentsociety.message.messager.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.message.messager.__all__
:value: >
   ['MessageKind', 'Message', 'Messager']

```{autodoc2-docstring} agentsociety.message.messager.__all__
```

````

`````{py:class} MessageKind()
:canonical: agentsociety.message.messager.MessageKind

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

````{py:attribute} AGENT_CHAT
:canonical: agentsociety.message.messager.MessageKind.AGENT_CHAT
:value: >
   'agent-chat'

```{autodoc2-docstring} agentsociety.message.messager.MessageKind.AGENT_CHAT
```

````

````{py:attribute} USER_CHAT
:canonical: agentsociety.message.messager.MessageKind.USER_CHAT
:value: >
   'user-chat'

```{autodoc2-docstring} agentsociety.message.messager.MessageKind.USER_CHAT
```

````

````{py:attribute} AOI_MESSAGE_REGISTER
:canonical: agentsociety.message.messager.MessageKind.AOI_MESSAGE_REGISTER
:value: >
   'aoi-message-register'

```{autodoc2-docstring} agentsociety.message.messager.MessageKind.AOI_MESSAGE_REGISTER
```

````

````{py:attribute} AOI_MESSAGE_CANCEL
:canonical: agentsociety.message.messager.MessageKind.AOI_MESSAGE_CANCEL
:value: >
   'aoi-message-cancel'

```{autodoc2-docstring} agentsociety.message.messager.MessageKind.AOI_MESSAGE_CANCEL
```

````

`````

`````{py:class} Message(/, **data: typing.Any)
:canonical: agentsociety.message.messager.Message

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} from_id
:canonical: agentsociety.message.messager.Message.from_id
:type: typing.Optional[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.from_id
```

````

````{py:attribute} to_id
:canonical: agentsociety.message.messager.Message.to_id
:type: typing.Optional[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.to_id
```

````

````{py:attribute} day
:canonical: agentsociety.message.messager.Message.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.day
```

````

````{py:attribute} t
:canonical: agentsociety.message.messager.Message.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.t
```

````

````{py:attribute} kind
:canonical: agentsociety.message.messager.Message.kind
:type: agentsociety.message.messager.MessageKind
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.kind
```

````

````{py:attribute} payload
:canonical: agentsociety.message.messager.Message.payload
:type: dict
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.payload
```

````

````{py:attribute} created_at
:canonical: agentsociety.message.messager.Message.created_at
:type: datetime.datetime
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.message.messager.Message.created_at
```

````

````{py:attribute} extra
:canonical: agentsociety.message.messager.Message.extra
:type: typing.Optional[dict]
:value: >
   None

```{autodoc2-docstring} agentsociety.message.messager.Message.extra
```

````

````{py:method} __hash__()
:canonical: agentsociety.message.messager.Message.__hash__

````

`````

`````{py:class} Messager(exp_id: str)
:canonical: agentsociety.message.messager.Messager

```{autodoc2-docstring} agentsociety.message.messager.Messager
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.message.messager.Messager.__init__
```

````{py:property} message_interceptor
:canonical: agentsociety.message.messager.Messager.message_interceptor
:type: typing.Optional[ray.ObjectRef]

```{autodoc2-docstring} agentsociety.message.messager.Messager.message_interceptor
```

````

````{py:method} set_message_interceptor(message_interceptor: ray.ObjectRef)
:canonical: agentsociety.message.messager.Messager.set_message_interceptor

```{autodoc2-docstring} agentsociety.message.messager.Messager.set_message_interceptor
```

````

````{py:method} send_message(message: agentsociety.message.messager.Message)
:canonical: agentsociety.message.messager.Messager.send_message
:async:

```{autodoc2-docstring} agentsociety.message.messager.Messager.send_message
```

````

````{py:method} fetch_pending_messages()
:canonical: agentsociety.message.messager.Messager.fetch_pending_messages
:async:

```{autodoc2-docstring} agentsociety.message.messager.Messager.fetch_pending_messages
```

````

````{py:method} set_received_messages(messages: list[agentsociety.message.messager.Message])
:canonical: agentsociety.message.messager.Messager.set_received_messages
:async:

```{autodoc2-docstring} agentsociety.message.messager.Messager.set_received_messages
```

````

````{py:method} fetch_received_messages()
:canonical: agentsociety.message.messager.Messager.fetch_received_messages
:async:

```{autodoc2-docstring} agentsociety.message.messager.Messager.fetch_received_messages
```

````

````{py:method} get_subtopic_channel(agent_id: int, subtopic: str)
:canonical: agentsociety.message.messager.Messager.get_subtopic_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_subtopic_channel
```

````

````{py:method} get_aoi_channel(aoi_id: int)
:canonical: agentsociety.message.messager.Messager.get_aoi_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_aoi_channel
```

````

````{py:method} get_user_survey_channel(agent_id: int)
:canonical: agentsociety.message.messager.Messager.get_user_survey_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_user_survey_channel
```

````

````{py:method} get_user_chat_channel(agent_id: int)
:canonical: agentsociety.message.messager.Messager.get_user_chat_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_user_chat_channel
```

````

````{py:method} get_agent_chat_channel(agent_id: int)
:canonical: agentsociety.message.messager.Messager.get_agent_chat_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_agent_chat_channel
```

````

````{py:method} get_user_payback_channel()
:canonical: agentsociety.message.messager.Messager.get_user_payback_channel

```{autodoc2-docstring} agentsociety.message.messager.Messager.get_user_payback_channel
```

````

`````
