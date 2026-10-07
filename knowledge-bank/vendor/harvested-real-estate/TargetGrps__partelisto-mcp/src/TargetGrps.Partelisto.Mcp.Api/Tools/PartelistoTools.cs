using System.ComponentModel;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using ModelContextProtocol;
using ModelContextProtocol.Server;
using TargetGrps.Partelisto.Mcp.Api.Auth;
using TargetGrps.Partelisto.Mcp.Application;
using TargetGrps.Partelisto.Mcp.Infrastructure;

namespace TargetGrps.Partelisto.Mcp.Api.Tools;

/// <summary>
/// The Partelisto MCP tool surface. Every tool is a thin wrapper over one existing, already
/// owner-scoped GraphQL operation (see GatewayQueries) — this class adds no business logic of its own.
///
/// Two layers of authorization apply, deliberately not the same one twice:
///  1. Scope, checked here: the incoming JWT (validated by the JwtBearer handler registered in
///     Program.cs — this reads its already-verified claims, it does not re-verify the token) must
///     carry "partelisto:read" for the five read tools, "partelisto:write" for send_guest_checkin_link.
///     This is what lets an OAuth consent screen offer read-only access separately from the one tool
///     with a real side effect.
///  2. Ownership/tenant, enforced by the gateway on every call: the bearer token is forwarded as-is,
///     and the gateway's OwnerAccess policy decides what data that specific user is allowed to see.
///     A valid "partelisto:write" scope does not by itself grant access to any particular booking.
/// </summary>
[McpServerToolType]
public sealed class PartelistoTools(IPartelistoGatewayClient gateway, IHttpContextAccessor httpContextAccessor)
{
    [McpServerTool(Name = "list_properties", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("Lists the signed-in host's properties: id, name, address, municipality/province, and whether it is archived. No guest data.")]
    public async Task<IReadOnlyList<PropertySummary>> ListProperties(
        [Description("Include archived properties. Defaults to false.")] bool includeArchived = false,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.ListProperties, new { includeArchived }, bearerToken, ct);
        return ResponseShaper.ToProperties(data);
    }

    [McpServerTool(Name = "list_bookings", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("Lists the signed-in host's bookings (newest first), paged. Returns id, property id, check-in/check-out dates, status, and whether a check-in link and guest contact exist — never the guest's email, phone, or documents.")]
    public async Task<BookingsPage> ListBookings(
        [Description("Rows to skip, for paging. Defaults to 0.")] int skip = 0,
        [Description("Rows to return, max 50. Defaults to 20.")] int take = 20,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        take = Math.Clamp(take, 1, 50);
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.ListBookings, new { skip, take }, bearerToken, ct);
        return ResponseShaper.ToBookingsPage(data);
    }

    [McpServerTool(Name = "get_guest_form_status", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("Whether the guest has completed the check-in form for a booking the host owns (None or Submitted). No form content.")]
    public async Task<GuestFormStatus> GetGuestFormStatus(
        [Description("The booking id.")] string bookingId,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.GetGuestFormStatus, new { bookingId }, bearerToken, ct);
        return ResponseShaper.ToGuestFormStatus(data, bookingId);
    }

    [McpServerTool(Name = "list_ses_statuses", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("SES.HOSPEDAJES (police registration) submission status for a set of bookings the host owns: status, attempts, last error, and the official reference once accepted. Bookings with no submission yet are omitted.")]
    public async Task<IReadOnlyList<SesStatusEntry>> ListSesStatuses(
        [Description("Booking ids to check, up to 50.")] string[] bookingIds,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        if (bookingIds.Length == 0)
            return [];
        if (bookingIds.Length > 50)
            throw new McpException("Pass at most 50 booking ids at a time.");

        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.ListSesStatuses, new { bookingIds }, bearerToken, ct);
        return ResponseShaper.ToSesStatuses(data);
    }

    [McpServerTool(Name = "get_usage_summary", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("The signed-in host's plan tier, trial status, and this month's usage against plan limits (properties, templates, bookings).")]
    public async Task<UsageSummary> GetUsageSummary(CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.GetUsageSummary, null, bearerToken, ct);
        return ResponseShaper.ToUsageSummary(data);
    }

    [McpServerTool(Name = "send_guest_checkin_link", ReadOnly = false, Destructive = false, Idempotent = false, OpenWorld = true)]
    [Description("Sends (or resends) the guest check-in link by email for a booking the host owns. This is a real action with a side effect: it emails the guest and, on resend, invalidates the guest's previous link. Requires the write permission granted separately during sign-in. Ask the host to confirm before calling this.")]
    public async Task<SendGuestLinkResult> SendGuestCheckinLink(
        [Description("The booking id.")] string bookingId,
        [Description("Guest email to send to. Omit to use the email already on the booking.")] string? email = null,
        [Description("Guest name, for the email greeting. Omit to keep the name already on the booking.")] string? guestName = null,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Write);
        var input = new { bookingId, email, guestName, propertyName = (string?)null, locale = (string?)null };
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.SendGuestLink, new { input }, bearerToken, ct);
        return ResponseShaper.ToSendGuestLinkResult(data);
    }

    [McpServerTool(Name = "create_booking", ReadOnly = false, Destructive = false, Idempotent = false, OpenWorld = true)]
    [Description("Creates a new booking (a check-in workflow) for one of the host's properties. Requires the write permission granted separately during sign-in. Ask the host to confirm the property and dates before calling this. Does not email the guest — call send_guest_checkin_link afterwards if a link should go out now.")]
    public async Task<BookingCreated> CreateBooking(
        [Description("The property id, from list_properties.")] string propertyId,
        [Description("Check-in date, yyyy-MM-dd.")] string checkIn,
        [Description("Check-out date, yyyy-MM-dd.")] string checkOut,
        [Description("Check-in template id. Omit if the property has exactly one active (non-archived) template — it is picked automatically; otherwise this is required.")] string? templateId = null,
        [Description("Guest name, optional.")] string? guestName = null,
        [Description("Guest email, optional.")] string? guestEmail = null,
        [Description("Guest phone, optional.")] string? guestPhone = null,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Write);

        string resolvedTemplateId = string.IsNullOrWhiteSpace(templateId)
            ? await ResolveSingleActiveTemplateAsync(propertyId, bearerToken, ct)
            : templateId;

        var input = new { propertyId, templateId = resolvedTemplateId, checkIn, checkOut, guestName, guestEmail, guestPhone };
        JsonElement data = await gateway.ExecuteAsync(GatewayQueries.CreateBooking, new { input }, bearerToken, ct);
        return ResponseShaper.ToBookingCreated(data);
    }

    [McpServerTool(Name = "get_attention_required", ReadOnly = true, Idempotent = true, OpenWorld = false)]
    [Description("Scans the signed-in host's most recent bookings (up to 50) and returns only what needs action right now: stays that are imminent or under way where the guest has not completed check-in, and bookings whose SES.HOSPEDAJES submission failed. Empty list means nothing needs attention within the window. No guest PII.")]
    public async Task<AttentionReport> GetAttentionRequired(
        [Description("How many days ahead counts as \"imminent\" (a negative gap means the stay already started). Defaults to 3.")] int arrivalWindowDays = 3,
        CancellationToken ct = default)
    {
        string bearerToken = RequireScope(PartelistoScopes.Read);
        arrivalWindowDays = Math.Clamp(arrivalWindowDays, 0, 30);

        JsonElement bookingsData = await gateway.ExecuteAsync(GatewayQueries.ListBookings, new { skip = 0, take = 50 }, bearerToken, ct);
        BookingsPage page = ResponseShaper.ToBookingsPage(bookingsData);

        IReadOnlyList<SesStatusEntry> sesStatuses = [];
        if (page.Items.Count > 0)
        {
            string[] bookingIds = page.Items.Select(b => b.Id).ToArray();
            JsonElement sesData = await gateway.ExecuteAsync(GatewayQueries.ListSesStatuses, new { bookingIds }, bearerToken, ct);
            sesStatuses = ResponseShaper.ToSesStatuses(sesData);
        }

        DateOnly today = DateOnly.FromDateTime(DateTime.UtcNow);
        IReadOnlyList<AttentionItem> items = AttentionAnalyzer.Analyze(page.Items, sesStatuses, today, arrivalWindowDays);
        return new AttentionReport(items, page.Items.Count);
    }

    /// <summary>
    /// create_booking's TemplateId is required by the gateway mutation but an AI caller shouldn't need
    /// to know about templates for the common case of one property, one active template. Ambiguity (zero
    /// or several active templates) is refused rather than guessed, with the ids listed so the caller
    /// can retry with one.
    /// </summary>
    private async Task<string> ResolveSingleActiveTemplateAsync(string propertyId, string bearerToken, CancellationToken ct)
    {
        JsonElement data = await gateway.ExecuteAsync(
            GatewayQueries.ListTemplatesForProperty, new { propertyId, includeArchived = false }, bearerToken, ct);
        IReadOnlyList<TemplateSummary> templates = ResponseShaper.ToTemplates(data);

        if (templates.Count == 0)
        {
            throw new McpException(
                "This property has no active check-in template yet. Create one in the Partelisto app first, " +
                "or pass templateId if you already know it.");
        }
        if (templates.Count > 1)
        {
            throw new McpException(
                $"This property has {templates.Count} active check-in templates ({string.Join(", ", templates.Select(t => t.Id))}). " +
                "Pass templateId to pick one.");
        }

        return templates[0].Id;
    }

    /// <summary>
    /// Confirms the caller presented a token, that the JwtBearer handler validated it (signature,
    /// issuer, expiry — see Program.cs), and that its "scope" claim grants <paramref name="requiredScope"/>.
    /// Returns the raw bearer token so the caller can forward it to the gateway unchanged.
    /// </summary>
    private string RequireScope(string requiredScope)
    {
        HttpContext? httpContext = httpContextAccessor.HttpContext;
        string? header = httpContext?.Request.Headers.Authorization.ToString();
        if (string.IsNullOrWhiteSpace(header) || !header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
            throw new McpException("Not signed in to Partelisto. Complete the sign-in flow this MCP connector offers, then retry.");

        ClaimsPrincipal? user = httpContext?.User;
        if (user?.Identity?.IsAuthenticated != true)
            throw new McpException("Your Partelisto sign-in could not be verified (it may be expired). Sign in again.");

        string[] grantedScopes = (user.FindFirst("scope")?.Value ?? string.Empty)
            .Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (!grantedScopes.Contains(requiredScope))
        {
            throw new McpException(
                $"This action needs the '{requiredScope}' permission, which was not granted when Partelisto was connected. " +
                "Reconnect Partelisto and allow that permission, then retry.");
        }

        return header["Bearer ".Length..].Trim();
    }
}
