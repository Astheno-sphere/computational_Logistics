export declare const DEFAULT_API_BASE = "https://disruption.forgemesh.io";
export type ApiRequestResult = {
    ok: true;
    status: number;
    url: string;
    data: unknown;
} | {
    ok: false;
    status: number;
    url: string;
    paymentRequired: boolean;
    challenge?: PaymentChallenge;
    error?: unknown;
};
export type PaymentChallenge = {
    status: 402;
    headers: Record<string, string>;
    decoded?: unknown;
    instructions: string;
};
export type DiscoveryMetadata = {
    apiBase: string;
    resources: Array<{
        path: string;
        url: string;
        status: number;
        ok: boolean;
        contentType?: string;
        data?: unknown;
        text?: string;
    }>;
};
export declare class DisruptionApiClient {
    readonly apiBase: string;
    constructor(apiBase?: string);
    get(path: string): Promise<ApiRequestResult>;
    getDiscoveryMetadata(): Promise<DiscoveryMetadata>;
    url(path: string): string;
}
