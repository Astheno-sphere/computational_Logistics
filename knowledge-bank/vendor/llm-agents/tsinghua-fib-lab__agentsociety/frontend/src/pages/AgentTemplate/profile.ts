export interface Profile {
    name: string;
    type: string;
    description: string;
}

export const profiles: Profile[] = [
    {
        name: "name",
        type: "str",
        description: "The name of the agent",
    },
    {
        name: "gender",
        type: "str",
        description: "The gender of the agent",
    },
    {
        name: "age",
        type: "int",
        description: "The age of the agent",
    },
    {
        name: "education",
        type: "str",
        description: "The education of the agent",
    },
    {
        name: "occupation",
        type: "str",
        description: "The occupation of the agent",
    },
    {
        name: "marriage_status",
        type: "str",
        description: "The marriage status of the agent",
    },
    {
        name: "persona",
        type: "Optional[str]",
        description: "The persona of the agent",
    },
    {
        name: "background_story",
        type: "Optional[str]",
        description: "The background story of the agent",
    },
]