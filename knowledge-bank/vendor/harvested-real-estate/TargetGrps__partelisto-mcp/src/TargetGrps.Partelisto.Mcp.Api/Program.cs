using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.HttpOverrides;
using ModelContextProtocol.Server;
using TargetGrps.Partelisto.Mcp.Api.Auth;
using TargetGrps.Partelisto.Mcp.Api.Tools;
using TargetGrps.Partelisto.Mcp.Infrastructure;

void ConfigureMcpServer(McpServerOptions options)
{
    options.ServerInfo = new() { Name = "partelisto", Title = "Partelisto", Version = "1.0.0" };
    options.ServerInstructions =
        "Guest check-in and SES.HOSPEDAJES (police registration) compliance for the signed-in host's " +
        "short-term rental properties. Tools return status/completeness only — never guest documents, " +
        "email, phone, or passport/DNI numbers. Read tools need the partelisto:read grant; " +
        "send_guest_checkin_link and create_booking additionally need partelisto:write, have a real " +
        "side effect (an email sent, or a new booking), and should be confirmed with the host before " +
        "calling them. Start with get_attention_required for a daily overview of what needs action.";
}

// Glama (and other stdio inspectors) speak MCP over stdin/stdout. Production k8s keeps HTTP.
if (args.Contains("--stdio", StringComparer.OrdinalIgnoreCase))
{
    HostApplicationBuilder stdioBuilder = Host.CreateApplicationBuilder(new HostApplicationBuilderSettings
    {
        Args = args,
        ContentRootPath = AppContext.BaseDirectory
    });
    // JSON-RPC is on stdout; keep host logs off that stream so inspectors can parse initialize/tools/list.
    stdioBuilder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace);
    stdioBuilder.Services.AddHttpContextAccessor();
    stdioBuilder.Services.AddPartelistoGateway(stdioBuilder.Configuration);
    stdioBuilder.Services
        .AddMcpServer(ConfigureMcpServer)
        .WithStdioServerTransport()
        .WithToolsFromAssembly();
    stdioBuilder.Build().Run();
    return;
}

WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpContextAccessor();
builder.Services.AddPartelistoGateway(builder.Configuration);

string keycloakAuthority = builder.Configuration["Keycloak:Authority"]
    ?? throw new InvalidOperationException("Keycloak:Authority is not configured.");
string keycloakAudience = builder.Configuration["Keycloak:Audience"] ?? "partelisto-mcp";

// Validates the token's signature/issuer/expiry against Keycloak (via its standard OIDC discovery
// document — no manual key management). Populates HttpContext.User so PartelistoTools.RequireScope
// can read the "scope" claim per call. This is the one place a token is actually verified: the raw
// bearer string still gets forwarded to the gateway unchanged afterwards, which does its own,
// unrelated OwnerAccess/tenant check — see PartelistoTools' class doc for why both layers exist.
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = keycloakAuthority;
        options.Audience = keycloakAudience;
        options.RequireHttpsMetadata = !builder.Environment.IsDevelopment();
    });

builder.Services
    .AddMcpServer(ConfigureMcpServer)
    .WithHttpTransport()
    .WithToolsFromAssembly();

WebApplication app = builder.Build();

// The pod only ever receives plain HTTP from the in-cluster nginx ingress, which terminates TLS —
// without this, request.Scheme reads "http" even for a real https:// call, which made the
// oauth-protected-resource "resource" field wrong (http://mcp.partelisto.es instead of https://).
// KnownNetworks/KnownProxies cleared because the only path to this pod is through that ingress
// (ClusterIP, no other ingress) — there's no untrusted network the header could arrive from instead.
var forwardedHeadersOptions = new ForwardedHeadersOptions
{
    ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto
};
forwardedHeadersOptions.KnownIPNetworks.Clear();
forwardedHeadersOptions.KnownProxies.Clear();
app.UseForwardedHeaders(forwardedHeadersOptions);

// Populates HttpContext.User from the bearer token when one is present and valid; does not itself
// reject unauthenticated requests (no [Authorize] / RequireAuthorization here) — tools/list must stay
// reachable without a token, and each tool enforces its own required scope. See PartelistoTools.
app.UseAuthentication();

app.MapMcp("/mcp");

// RFC 9728 protected-resource metadata, so spec-compliant MCP OAuth clients can discover the
// authorization server (Keycloak) and the two grantable scopes, instead of the host having to paste a
// token in by hand. Points at the same realm the web app and gateway already trust.
app.MapGet("/.well-known/oauth-protected-resource", (HttpRequest request) =>
{
    string resource = $"{request.Scheme}://{request.Host}";

    return Results.Json(new
    {
        resource,
        authorization_servers = new[] { keycloakAuthority },
        bearer_methods_supported = new[] { "header" },
        scopes_supported = new[] { PartelistoScopes.Read, PartelistoScopes.Write }
    });
});

// Named /healthz, not /health, to match the other TargetGrps services' convention.
app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));

app.Run();

// Kept for consistency with the other TargetGrps services' logging/observability convention, even
// though this service does not use ApiServiceBootstrapper (it owns no data — no Mongo, no tenancy
// middleware to bootstrap; see README for why it deviates from the usual service-structure template).
public partial class Program
{
    public const string AppName = "targetgrps-partelisto-mcp";
}
