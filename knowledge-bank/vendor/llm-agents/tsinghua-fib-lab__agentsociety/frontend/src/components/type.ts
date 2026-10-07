export interface Experiment {
    id: string;
    name: string;
    numDay: number;
    status: number;
    curDay: number;
    curT: number;
    config: string;
    error: string;
    inputTokens: number;
    outputTokens: number;
    createdAt: string;
    updatedAt: string;
}

export interface Survey {
    id: string;
    name: string;
    data: Record<string, unknown>;
    createdAt: string;
    updatedAt: string;
}
