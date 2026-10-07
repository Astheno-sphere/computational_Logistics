using System.Text.Json;

namespace TargetGrps.Partelisto.Mcp.Infrastructure;

public interface IPartelistoGatewayClient
{
    /// <summary>
    /// Executes one GraphQL operation against the api-gateway, forwarding <paramref name="bearerToken"/>
    /// exactly as the caller (an MCP client acting on behalf of a signed-in owner) presented it. Returns
    /// the response's "data" node. The gateway is the sole point of authorization and tenant scoping —
    /// this client does not second-guess it.
    /// </summary>
    Task<JsonElement> ExecuteAsync(string query, object? variables, string bearerToken, CancellationToken ct);
}

/// <summary>Raised when the gateway returns a GraphQL "errors" entry (auth failure, not found, validation, etc.).</summary>
public sealed class PartelistoGatewayException(string message) : Exception(message);
