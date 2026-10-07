namespace TargetGrps.Partelisto.Mcp.Infrastructure;

/// <summary>
/// Where the api-gateway lives and which tenant to scope calls to. Partelisto is single-tenant
/// (tenant id "partelisto" everywhere, same constant the SPA sends — see VITE_TENANT_ID), so this is
/// one fixed value, not something resolved per request.
/// </summary>
public sealed class GatewayOptions
{
    public const string SectionName = "Gateway";

    public required string BaseUrl { get; set; }

    public string TenantId { get; set; } = "partelisto";
}
