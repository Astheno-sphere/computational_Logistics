import uuid
from typing import (
    Dict,
    List,
    Literal,
    Optional,
    Union,
    cast,
    Any,
    get_args,
    get_origin,
)

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiResponseWrapper
from ..models.agent_template import (
    AgentTemplateDB,
    ApiAgentTemplate,
    ChoiceDistributionConfig,
    UniformIntDistributionConfig,
    NormalDistributionConfig,
    AgentParams,
    DistributionType,
)
from .timezone import ensure_timezone_aware

try:
    from agentsociety_community.agents import citizens, supervisors
    from agentsociety_community.workflows import functions as workflow_functions
    from agentsociety_community.blocks import citizens as citizen_blocks
except ImportError:
    import warnings

    warnings.warn(
        "agentsociety_community is not installed. Please install it with `pip install agentsociety-community`"
    )

    citizens = None
    supervisors = None
    workflow_functions = None
    citizen_blocks = None

__all__ = ["router"]

router = APIRouter(tags=["agent_templates"])


@router.get("/agent-templates")
async def list_agent_templates(
    request: Request,
) -> ApiResponseWrapper[List[ApiAgentTemplate]]:
    """List all agent templates"""
    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = (
            select(AgentTemplateDB)
            .where(AgentTemplateDB.tenant_id.in_([tenant_id, "", "default"]))
            .order_by(AgentTemplateDB.created_at.desc())
        )
        result = await db.execute(stmt)
        templates = result.scalars().all()

        # 处理时区并转换为API格式
        response_templates = []
        for template in templates:
            # 处理时区
            template.created_at = ensure_timezone_aware(template.created_at)
            template.updated_at = ensure_timezone_aware(template.updated_at)
            
            response_templates.append(convert_agent_template_from_db_to_api(template))

        return ApiResponseWrapper(data=response_templates)


@router.get("/agent-templates/{template_id}")
async def get_agent_template(
    request: Request,
    template_id: str,
) -> ApiResponseWrapper[ApiAgentTemplate]:
    """Get agent template by ID"""
    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = select(AgentTemplateDB).where(
            AgentTemplateDB.tenant_id.in_([tenant_id, "", "default"]),
            AgentTemplateDB.id == template_id,
        )

        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )
        api_template = convert_agent_template_from_db_to_api(template)
        return ApiResponseWrapper(data=api_template)


def convert_agent_template_from_db_to_api(
    template: AgentTemplateDB,
) -> ApiAgentTemplate:
    """Convert agent template from DB format to API format"""
    # Parse memory distributions from dictionary format back to Python objects
    memory_distributions_dict = {}

    # Convert each profile into DistributionConfig objects
    for profile_name, profile_config in template.profile.items():
        dist_type = profile_config.get("type")
        if dist_type == DistributionType.CHOICE:
            memory_distributions_dict[profile_name] = ChoiceDistributionConfig(
                type=DistributionType.CHOICE,
                choices=profile_config["choices"],
                weights=profile_config["weights"],
            )
        elif dist_type == DistributionType.UNIFORM_INT:
            memory_distributions_dict[profile_name] = UniformIntDistributionConfig(
                type=DistributionType.UNIFORM_INT,
                min_value=profile_config["min_value"],
                max_value=profile_config["max_value"],
            )
        elif dist_type == DistributionType.NORMAL:
            memory_distributions_dict[profile_name] = NormalDistributionConfig(
                type=DistributionType.NORMAL,
                mean=profile_config["mean"],
                std=profile_config["std"],
            )

    api_template = ApiAgentTemplate(
        tenant_id=template.tenant_id,
        id=template.id,
        name=template.name,
        description=template.description,
        agent_type=template.agent_type,
        agent_class=template.agent_class,
        memory_distributions=memory_distributions_dict,
        agent_params=AgentParams(**template.agent_params),
        blocks=template.blocks,
        created_at=ensure_timezone_aware(template.created_at),
        updated_at=ensure_timezone_aware(template.updated_at),
    )
    return api_template


@router.post("/agent-templates")
async def create_agent_template(
    request: Request,
    template: ApiAgentTemplate = Body(...),
) -> ApiResponseWrapper[ApiAgentTemplate]:
    """Create a new agent template"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )

    try:
        tenant_id = await request.app.state.get_tenant_id(request)
        template_id = str(uuid.uuid4())

        # Convert memory_distributions to serializable dictionary format
        profile_dict = {}
        for key, value in template.memory_distributions.items():
            # 如果是Config类型，直接转换为字典
            profile_dict[key] = value.model_dump()

        async with request.app.state.get_db() as db:
            db = cast(AsyncSession, db)

            new_template = AgentTemplateDB(
                tenant_id=tenant_id,
                id=template_id,
                name=template.name,
                description=template.description,
                agent_type=template.agent_type,
                agent_class=template.agent_class,
                profile=profile_dict,
                agent_params=template.agent_params.model_dump(),
                blocks=template.blocks,
            )

            db.add(new_template)
            await db.commit()
            await db.refresh(new_template)

            # Construct response data
            response_template = ApiAgentTemplate(
                tenant_id=new_template.tenant_id,
                id=new_template.id,
                name=new_template.name,
                description=new_template.description,
                agent_type=new_template.agent_type,
                agent_class=new_template.agent_class,
                memory_distributions=new_template.profile,
                agent_params=AgentParams(**new_template.agent_params),
                blocks=new_template.blocks,
                created_at=ensure_timezone_aware(new_template.created_at),
                updated_at=ensure_timezone_aware(new_template.updated_at),
            )

            return ApiResponseWrapper(data=response_template)

    except Exception as e:
        print(f"Error details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)}",
        )


@router.put("/agent-templates/{template_id}")
async def update_agent_template(
    request: Request,
    template_id: str,
    template: ApiAgentTemplate = Body(...),
) -> ApiResponseWrapper[ApiAgentTemplate]:
    """Update an existing agent template"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )

    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = (
            update(AgentTemplateDB)
            .where(
                AgentTemplateDB.tenant_id == tenant_id,
                AgentTemplateDB.id == template_id,
            )
            .values(
                name=template.name,
                description=template.description,
                agent_type=template.agent_type,
                agent_class=template.agent_class,
                profile=template.memory_distributions,
                agent_params=template.agent_params.model_dump(),
                blocks=template.blocks,
            )
        )

        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        await db.commit()
        return ApiResponseWrapper(data=template)


@router.delete("/agent-templates/{template_id}")
async def delete_agent_template(
    request: Request,
    template_id: str,
) -> ApiResponseWrapper[Dict[str, str]]:
    """Delete an agent template"""
    if request.app.state.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
        )

    tenant_id = await request.app.state.get_tenant_id(request)

    async with request.app.state.get_db() as db:
        db = cast(AsyncSession, db)
        stmt = delete(AgentTemplateDB).where(
            AgentTemplateDB.tenant_id == tenant_id, AgentTemplateDB.id == template_id
        )

        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        await db.commit()
        return ApiResponseWrapper(data={"message": "Template deleted successfully"})


@router.get("/agent-blocks")
async def get_agent_blocks(
    request: Request,
) -> ApiResponseWrapper[List[str]]:
    """Get available block types"""
    try:
        blocks = []

        # 获取citizen blocks
        if citizen_blocks is not None:
            # for block_name, block_class in citizen_blocks.get_type_to_cls_dict().items():
            #     block_info = {
            #         "block_name": block_class.name,
            #         "description": block_class.description,
            #     }
            #     blocks.append(block_info)
            blocks = list(citizen_blocks.get_type_to_cls_dict().keys())

        return ApiResponseWrapper(data=blocks)
    except Exception as e:
        print(f"Error in get_agent_blocks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent blocks: {str(e)}",
        )


class ParamOption(BaseModel):
    label: str
    value: Any


class Param(BaseModel):
    """
    Parameter edited at frontend
    """

    name: str
    required: bool
    default: Optional[Any] = None
    description: Optional[str] = None
    type: Literal["str", "int", "float", "bool", "select", "select_multiple"]
    options: List[ParamOption] = []


class NameTypeDescription(BaseModel):
    """
    Name, type and description of agent to describe context / status attribute
    """

    name: str
    type: str
    description: Optional[str] = None


def simplify_type(type_annotation):
    """Convert type annotation to a simplified string format for human readable"""
    type_str = str(type_annotation)

    # Handle class format
    if type_str.startswith("<class '") and type_str.endswith("'>"):
        return type_str[8:-2]

    # Handle typing.Optional
    if type_str.startswith("typing.Optional["):
        inner_type = type_str[len("typing.Optional[") : -1]
        return f"{simplify_type(inner_type)}?"

    # Handle typing.List
    if type_str.startswith("typing.List["):
        inner_type = type_str[len("typing.List[") : -1]
        return f"List<{simplify_type(inner_type)}>"

    # Handle typing.Dict
    if type_str.startswith("typing.Dict["):
        # Extract key and value types
        inner_types = type_str[len("typing.Dict[") : -1].split(", ")
        if len(inner_types) == 2:
            key_type = simplify_type(inner_types[0])
            value_type = simplify_type(inner_types[1])
            return f"Dict<{key_type}, {value_type}>"

    # Handle Union type
    if type_str.startswith("typing.Union["):
        inner_types = type_str[len("typing.Union[") : -1].split(", ")
        return " | ".join(simplify_type(t) for t in inner_types)

    return type_str.replace("typing.", "")


def parse_pydantic_to_table(
    model_class: type[BaseModel], exclude_fields: list[str] = []
) -> list[NameTypeDescription]:
    """
    解析pydantic model为适合前端表格呈现的JSON格式

    Args:
        model_class: Pydantic BaseModel子类

    Returns:
        list: 包含表格配置的列表
    """

    if not issubclass(model_class, BaseModel):
        import warnings

        warnings.warn(
            f"model_class {model_class} is not a subclass of BaseModel, return empty list"
        )

    table_items = []
    for field_name, field_info in model_class.model_fields.items():
        if field_name in exclude_fields:
            continue
        table_items.append(
            NameTypeDescription(
                name=field_name,
                type=simplify_type(field_info.annotation),
                description=field_info.description or "",
            )
        )
    return table_items


def parse_pydantic_to_antd_form(
    model_class: type[BaseModel], exclude_fields: list[str] = []
) -> list[Param]:
    """
    解析pydantic model为适合AntDesign表单的JSON格式

    Args:
        model_class: Pydantic BaseModel子类

    Returns:
        list: 包含表格配置的列表
    """

    if not issubclass(model_class, BaseModel):
        import warnings

        warnings.warn(
            f"model_class {model_class} is not a subclass of BaseModel, return empty list"
        )
        return []

    def get_field_type_info(field_annotation, field_info):
        """解析字段类型信息"""
        origin = get_origin(field_annotation)
        args = get_args(field_annotation)

        # 处理Literal类型 - 下拉选择
        if origin is Literal:
            return {
                "type": "select",
                "options": [{"label": str(arg), "value": arg} for arg in args],
            }

        # 处理list类型
        if origin is list:
            if args and get_origin(args[0]) is Literal:
                # list[Literal[...]] - 多选
                literal_args = get_args(args[0])
                return {
                    "type": "select_multiple",
                    "options": [
                        {"label": str(arg), "value": arg} for arg in literal_args
                    ],
                }
            else:
                # TODO: 暂时不支持list[str]类型
                import warnings
                warnings.warn(f"Unsupported field type: {field_annotation}, field_info: {field_info}")
                # raise ValueError(
                #     f"Unsupported field type: {field_annotation}, field_info: {field_info}"
                # )

        # 处理Union类型
        if origin is Union:
            # 简化处理：取第一个非None类型的基本类型（int, float, str, bool, Literal）
            good_types = []
            for arg in args:
                if arg in (int, float, str, bool):
                    good_types.append(arg)
                elif get_origin(arg) in (int, float, str, bool, Literal, Optional):
                    good_types.append(arg)
                elif get_origin(arg) is Union:
                    good_types.extend(get_args(arg))
            print(f"good_types: {good_types}")
            if good_types:
                return get_field_type_info(good_types[0], field_info)
            else:
                raise ValueError(
                    f"Unsupported field type: {field_annotation}, field_info: {field_info}"
                )

        # 处理基础类型
        if field_annotation is str:
            return {"type": "str"}
        elif field_annotation is int:
            return {"type": "int"}
        elif field_annotation is float:
            return {"type": "float"}
        elif field_annotation is bool:
            return {"type": "bool"}

        raise ValueError(
            f"Unsupported field type: {field_annotation}, field_info: {field_info}"
        )

    # 解析模型字段
    form_items = []

    for field_name, field_info in model_class.model_fields.items():
        if field_name in exclude_fields:
            continue

        # 获取字段类型信息
        type_info = get_field_type_info(field_info.annotation, field_info)

        # 构建表单项配置
        form_item = {
            "name": field_name,
            "required": field_info.is_required(),
            "description": field_info.description,
            **type_info,
        }

        # 添加默认值
        if (
            field_info.default is not None
            and field_info.default != ...
            and field_info.default != PydanticUndefined
        ):  # ... 表示无默认值
            form_item["default"] = field_info.default
        elif (
            hasattr(field_info, "default_factory")
            and field_info.default_factory is not None
        ):
            form_item["default"] = field_info.default_factory()  # type: ignore

        form_items.append(form_item)

    params = [Param(**item) for item in form_items]

    return params


class AgentParam(BaseModel):
    """
    Agent parameter
    """

    params_type: List[Param]
    # block_output_type: List[Param]
    context: List[NameTypeDescription]
    status_attributes: List[NameTypeDescription]


@router.get("/agent-param")
async def get_agent_param(
    request: Request,
    agent_type: str,
    agent_class: str,
) -> ApiResponseWrapper[AgentParam]:
    """Get agent's parameters including ParamsType, BlockOutputType, Context and StatusAttributes based on agent type and class"""
    # Get the appropriate agent class based on agent_type and agent_class
    if agent_type == "citizen":
        if citizens is None:
            type_dict = {}
        else:
            type_dict = citizens.get_type_to_cls_dict()
    elif agent_type == "supervisor":
        if supervisors is None:
            type_dict = {}
        else:
            type_dict = supervisors.get_type_to_cls_dict()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent_type. Must be 'citizen' or 'supervisor', got: {agent_type}",
        )

    if agent_class not in type_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent_class '{agent_class}' for agent_type '{agent_type}'. Available classes: {list(type_dict.keys())}",
        )

    # Get the agent class
    agent_cls_factory = type_dict[agent_class]
    agent_cls = agent_cls_factory()

    # Get agent parameters information
    param_data = AgentParam(
        params_type=[],
        # block_output_type=[],
        context=[],
        status_attributes=[],
    )

    # Process ParamsType
    param_data.params_type = parse_pydantic_to_antd_form(agent_cls.ParamsType)

    # Process BlockOutputType
    # if agent_cls.BlockOutputType is not None:
    #     param_data["block_output_type"] = parse_pydantic_to_antd_form(
    #         agent_cls.BlockOutputType
    #     )

    # Process Context
    param_data.context = parse_pydantic_to_table(agent_cls.Context)

    # Process StatusAttributes
    param_data.status_attributes = [
        NameTypeDescription(
            name=attr.name,
            type=simplify_type(attr.type),
            # default=(
            #     None
            #     if str(attr.default.__class__).endswith("PydanticUndefinedType'>")
            #     else attr.default
            # ),
            description=attr.description,
            # "whether_embedding": attr.whether_embedding if hasattr(attr, "whether_embedding") else False
        )
        for attr in agent_cls.StatusAttributes
    ]

    return ApiResponseWrapper(data=param_data)

class BlockParam(BaseModel):
    """
    Block parameter
    """

    params_type: List[Param]
    context: List[NameTypeDescription]

@router.get("/block-param/{block_type}")
async def get_block_param(
    request: Request,
    block_type: str,
) -> ApiResponseWrapper[BlockParam]:
    """Get Block's parameters including ParamsType and Context for specified block type"""
    # 在citizen blocks中查找
    if citizen_blocks is not None:
        block_map = citizen_blocks.get_type_to_cls_dict()
        if block_type in block_map:
            block_class_factory = block_map[block_type]
            block_class = block_class_factory()

    if block_class is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block type: {block_type}",
        )

    # Get Block parameters information
    param_data = BlockParam(
        params_type=[],
        context=[],
    )

    # Process ParamsType
    if hasattr(block_class, "ParamsType"):
        param_data.params_type = parse_pydantic_to_antd_form(
            block_class.ParamsType, exclude_fields=["block_memory"]
        )

    # Process Context
    if hasattr(block_class, "Context"):
        param_data.context = parse_pydantic_to_table(block_class.Context)

    return ApiResponseWrapper(data=param_data)


@router.get("/agent-classes")
async def get_agent_classes(
    request: Request,
    agent_type: str,
) -> ApiResponseWrapper[List[Dict[str, str]]]:
    """Get available agent classes base on agent type"""
    try:
        if agent_type == "citizen":
            if citizens is None:
                type_dict = {}
            else:
                type_dict = citizens.get_type_to_cls_dict()
        elif agent_type == "supervisor":
            if supervisors is None:
                type_dict = {}
            else:
                type_dict = supervisors.get_type_to_cls_dict()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent_type. Must be 'citizen' or 'supervisor', got: {agent_type}",
            )

        # Convert to list of dicts with value and label for frontend Select component
        agent_type_result = [
            {"value": type_name, "label": type_name} for type_name in type_dict.keys()
        ]
        return ApiResponseWrapper(data=agent_type_result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_agent_classes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent_classes '{agent_type}': {str(e)}",
        )


@router.get("/community/workflow/functions")
async def get_workflow_functions(
    request: Request,
) -> ApiResponseWrapper[List[str]]:
    """Get available workflow function names"""
    try:
        if workflow_functions is None:
            function_map = {}
        else:
            function_map = workflow_functions.get_type_to_cls_dict()
        function_names = list(function_map.keys())
        return ApiResponseWrapper(data=function_names)
    except Exception as e:
        print(f"Error in get_workflow_functions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow functions: {str(e)}",
        )
