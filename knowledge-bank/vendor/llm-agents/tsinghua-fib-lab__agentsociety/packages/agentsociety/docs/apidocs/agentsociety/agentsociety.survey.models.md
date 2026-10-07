# {py:mod}`agentsociety.survey.models`

```{py:module} agentsociety.survey.models
```

```{autodoc2-docstring} agentsociety.survey.models
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`QuestionType <agentsociety.survey.models.QuestionType>`
  -
* - {py:obj}`Question <agentsociety.survey.models.Question>`
  -
* - {py:obj}`Page <agentsociety.survey.models.Page>`
  -
* - {py:obj}`Survey <agentsociety.survey.models.Survey>`
  - ```{autodoc2-docstring} agentsociety.survey.models.Survey
    :summary:
    ```
````

### API

`````{py:class} QuestionType()
:canonical: agentsociety.survey.models.QuestionType

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

````{py:attribute} TEXT
:canonical: agentsociety.survey.models.QuestionType.TEXT
:value: >
   'text'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.TEXT
```

````

````{py:attribute} RADIO
:canonical: agentsociety.survey.models.QuestionType.RADIO
:value: >
   'radiogroup'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.RADIO
```

````

````{py:attribute} CHECKBOX
:canonical: agentsociety.survey.models.QuestionType.CHECKBOX
:value: >
   'checkbox'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.CHECKBOX
```

````

````{py:attribute} BOOLEAN
:canonical: agentsociety.survey.models.QuestionType.BOOLEAN
:value: >
   'boolean'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.BOOLEAN
```

````

````{py:attribute} RATING
:canonical: agentsociety.survey.models.QuestionType.RATING
:value: >
   'rating'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.RATING
```

````

````{py:attribute} MATRIX
:canonical: agentsociety.survey.models.QuestionType.MATRIX
:value: >
   'matrix'

```{autodoc2-docstring} agentsociety.survey.models.QuestionType.MATRIX
```

````

`````

`````{py:class} Question(/, **data: typing.Any)
:canonical: agentsociety.survey.models.Question

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} name
:canonical: agentsociety.survey.models.Question.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Question.name
```

````

````{py:attribute} title
:canonical: agentsociety.survey.models.Question.title
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Question.title
```

````

````{py:attribute} type
:canonical: agentsociety.survey.models.Question.type
:type: agentsociety.survey.models.QuestionType
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Question.type
```

````

````{py:attribute} choices
:canonical: agentsociety.survey.models.Question.choices
:type: typing.List[str]
:value: >
   []

```{autodoc2-docstring} agentsociety.survey.models.Question.choices
```

````

````{py:attribute} columns
:canonical: agentsociety.survey.models.Question.columns
:type: typing.List[str]
:value: >
   []

```{autodoc2-docstring} agentsociety.survey.models.Question.columns
```

````

````{py:attribute} rows
:canonical: agentsociety.survey.models.Question.rows
:type: typing.List[str]
:value: >
   []

```{autodoc2-docstring} agentsociety.survey.models.Question.rows
```

````

````{py:attribute} required
:canonical: agentsociety.survey.models.Question.required
:type: bool
:value: >
   True

```{autodoc2-docstring} agentsociety.survey.models.Question.required
```

````

````{py:attribute} min_rating
:canonical: agentsociety.survey.models.Question.min_rating
:type: int
:value: >
   1

```{autodoc2-docstring} agentsociety.survey.models.Question.min_rating
```

````

````{py:attribute} max_rating
:canonical: agentsociety.survey.models.Question.max_rating
:type: int
:value: >
   5

```{autodoc2-docstring} agentsociety.survey.models.Question.max_rating
```

````

````{py:method} parse_choices(value: typing.Any) -> typing.List[str]
:canonical: agentsociety.survey.models.Question.parse_choices
:classmethod:

```{autodoc2-docstring} agentsociety.survey.models.Question.parse_choices
```

````

`````

`````{py:class} Page(/, **data: typing.Any)
:canonical: agentsociety.survey.models.Page

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} name
:canonical: agentsociety.survey.models.Page.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Page.name
```

````

````{py:attribute} elements
:canonical: agentsociety.survey.models.Page.elements
:type: typing.List[agentsociety.survey.models.Question]
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Page.elements
```

````

`````

`````{py:class} Survey(/, **data: typing.Any)
:canonical: agentsociety.survey.models.Survey

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.survey.models.Survey
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.survey.models.Survey.__init__
```

````{py:attribute} id
:canonical: agentsociety.survey.models.Survey.id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Survey.id
```

````

````{py:attribute} title
:canonical: agentsociety.survey.models.Survey.title
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.survey.models.Survey.title
```

````

````{py:attribute} description
:canonical: agentsociety.survey.models.Survey.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.survey.models.Survey.description
```

````

````{py:attribute} pages
:canonical: agentsociety.survey.models.Survey.pages
:type: typing.List[agentsociety.survey.models.Page]
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Survey.pages
```

````

````{py:attribute} responses
:canonical: agentsociety.survey.models.Survey.responses
:type: typing.Dict[str, dict]
:value: >
   None

```{autodoc2-docstring} agentsociety.survey.models.Survey.responses
```

````

````{py:attribute} created_at
:canonical: agentsociety.survey.models.Survey.created_at
:type: datetime.datetime
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.survey.models.Survey.created_at
```

````

````{py:method} to_prompt() -> typing.List[str]
:canonical: agentsociety.survey.models.Survey.to_prompt

```{autodoc2-docstring} agentsociety.survey.models.Survey.to_prompt
```

````

`````
