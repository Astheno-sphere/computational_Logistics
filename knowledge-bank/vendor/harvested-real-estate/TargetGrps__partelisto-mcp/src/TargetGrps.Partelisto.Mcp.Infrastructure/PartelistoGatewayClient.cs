using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Options;

namespace TargetGrps.Partelisto.Mcp.Infrastructure;

/// <summary>
/// Mirrors the frontend's graphqlFetch (partelisto-site/src/lib/api.js): one origin, POST /graphql,
/// Authorization: Bearer &lt;token&gt; forwarded as-is, and a fixed Tenant header. Deliberately not a
/// generic pass-through — callers only ever send the fixed queries in <see cref="GatewayQueries"/>.
/// </summary>
public sealed class PartelistoGatewayClient(HttpClient httpClient, IOptions<GatewayOptions> options)
    : IPartelistoGatewayClient
{
    public async Task<JsonElement> ExecuteAsync(string query, object? variables, string bearerToken, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/graphql")
        {
            Content = JsonContent.Create(new { query, variables })
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
        request.Headers.Add("Tenant", options.Value.TenantId);

        using HttpResponseMessage response = await httpClient.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();

        await using System.IO.Stream stream = await response.Content.ReadAsStreamAsync(ct);
        using JsonDocument document = await JsonDocument.ParseAsync(stream, cancellationToken: ct);
        JsonElement root = document.RootElement;

        if (root.TryGetProperty("errors", out JsonElement errors) && errors.GetArrayLength() > 0)
        {
            string message = errors[0].TryGetProperty("message", out JsonElement m)
                ? m.GetString() ?? "GraphQL error"
                : "GraphQL error";
            throw new PartelistoGatewayException(message);
        }

        // Clone so the value survives the JsonDocument being disposed.
        return root.TryGetProperty("data", out JsonElement data) ? data.Clone() : default;
    }
}
