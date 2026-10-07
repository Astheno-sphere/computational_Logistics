namespace TargetGrps.Partelisto.Mcp.Api.Auth;

/// <summary>
/// The two OAuth scopes this MCP server asks for. Kept separate so a host can grant read access during
/// the OAuth consent screen without also granting send_guest_checkin_link (the one tool with a real
/// side effect — it emails a guest and rotates their check-in link). The Keycloak client backing this
/// server's authorization_servers entry must define both as client scopes named exactly this; see
/// README "OAuth setup" for the manual Keycloak step this depends on.
/// </summary>
public static class PartelistoScopes
{
    public const string Read = "partelisto:read";
    public const string Write = "partelisto:write";
}
