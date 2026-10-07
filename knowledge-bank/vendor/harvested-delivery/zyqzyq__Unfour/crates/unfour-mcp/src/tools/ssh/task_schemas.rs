use serde_json::{json, Map, Value};

pub(super) fn workspace_schema() -> Value {
    json!({
        "type": "object",
        "properties": { "workspaceId": { "type": "string" } },
        "additionalProperties": false
    })
}

pub(super) fn id_schema(id: &str, confirmation: bool) -> Value {
    let mut properties = Map::from_iter([
        ("workspaceId".to_string(), json!({ "type": "string" })),
        (id.to_string(), json!({ "type": "string" })),
    ]);
    if confirmation {
        properties.extend([
            ("confirm".to_string(), json!({ "type": "boolean" })),
            ("confirmationText".to_string(), json!({ "type": "string" })),
            ("confirmation_text".to_string(), json!({ "type": "string" })),
        ]);
    }
    json!({
        "type": "object",
        "properties": properties,
        "required": [id],
        "additionalProperties": false
    })
}

pub(super) fn save_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "workspaceId": { "type": "string" },
            "taskId": { "type": "string" },
            "name": { "type": "string" },
            "description": { "type": ["string", "null"] },
            "defaultConnectionId": { "type": ["string", "null"] },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": { "type": "string" },
                        "name": { "type": "string" },
                        "stepType": { "type": "string", "enum": ["command", "upload", "download"] },
                        "position": { "type": "integer" },
                        "enabled": { "type": "boolean" },
                        "configVersion": { "type": "integer" },
                        "configJson": { "type": "object" }
                    },
                    "required": ["name", "stepType", "position", "enabled", "configJson"],
                    "additionalProperties": false
                }
            }
        },
        "required": ["name", "steps"],
        "additionalProperties": false
    })
}

pub(super) fn run_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "workspaceId": { "type": "string" },
            "taskId": { "type": "string" },
            "connectionId": { "type": "string" },
            "inputs": { "type": "object", "additionalProperties": { "type": "string" } },
            "secretInputNames": { "type": "array", "items": { "type": "string" } },
            "confirm": { "type": "boolean" },
            "confirmationText": { "type": "string" },
            "confirmation_text": { "type": "string" }
        },
        "required": ["taskId"],
        "additionalProperties": false
    })
}
