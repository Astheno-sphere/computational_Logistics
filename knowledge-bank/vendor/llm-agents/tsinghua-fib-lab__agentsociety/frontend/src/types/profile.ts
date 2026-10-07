export interface ApiAgentProfile {
    tenant_id?: string;
    id?: string;
    name: string;
    description?: string;
    agent_type: string;
    file_path: string;
    record_count: number;
    created_at?: string;
    updated_at?: string;
}