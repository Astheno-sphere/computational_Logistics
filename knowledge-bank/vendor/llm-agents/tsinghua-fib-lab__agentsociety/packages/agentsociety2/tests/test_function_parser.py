import ast

from agentsociety2.env.base import tool
from agentsociety2.env.function_parser import FunctionParser
from agentsociety2.env.pydantic_collector import PydanticModelCollector
from agentsociety2.env.router_base import ModuleToolsInfo, RouterBase, ToolInfo


class _SampleEnv:
    _persons: set[int]

    @tool(readonly=False)
    async def move_to(self, person_id: int) -> dict:
        """Move a person."""
        if person_id not in self._persons:
            raise ValueError(f"Person {person_id} not found")

        return {"status": "ok"}


class _DummyRouter(RouterBase):
    async def ask(self, ctx, instruction, readonly=False, template_mode=False):
        return ctx, ""


def test_function_parser_returns_body_code_relative_to_function_body():
    parser = FunctionParser()

    function_parts = parser.parse_function(_SampleEnv.move_to)

    assert function_parts is not None
    assert function_parts.body_code[:4] == [
        "if person_id not in self._persons:",
        '    raise ValueError(f"Person {person_id} not found")',
        "",
        'return {"status": "ok"}',
    ]


def test_raw_tools_code_is_parseable_for_indented_method_body():
    parser = FunctionParser()
    function_parts = parser.parse_function(_SampleEnv.move_to)
    assert function_parts is not None

    router = object.__new__(_DummyRouter)
    router._pydantic_collector = PydanticModelCollector()
    modules_info = {
        "SampleEnv": ModuleToolsInfo(
            description="Sample environment.",
            tools=[
                ToolInfo(
                    function_parts=function_parts,
                    name="move_to",
                    description="Move a person.",
                    readonly=False,
                )
            ],
        )
    }

    raw_code = RouterBase._format_tools_raw_code(router, modules_info)

    ast.parse(raw_code)
