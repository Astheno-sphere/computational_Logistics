using System.Text.Json;

namespace TargetGrps.Partelisto.Mcp.Application;

/// <summary>
/// Pure mapping from a gateway GraphQL response's "data" node to the tool DTOs. No I/O, no DI — easy to
/// unit test, which matters here because this is the second (and last) place PII redaction is enforced:
/// GatewayQueries never selects email/phone/document fields, and this layer only ever reads the fields
/// it declared. A field this code does not reference cannot leak even if a query is later widened by
/// mistake.
/// </summary>
public static class ResponseShaper
{
    public static IReadOnlyList<PropertySummary> ToProperties(JsonElement data)
    {
        var result = new List<PropertySummary>();
        foreach (JsonElement p in data.GetProperty("properties").EnumerateArray())
        {
            result.Add(new PropertySummary(
                p.GetProperty("id").GetString()!,
                p.GetProperty("name").GetString()!,
                p.GetProperty("address").GetString()!,
                GetStringOrNull(p, "municipality"),
                GetStringOrNull(p, "province"),
                p.GetProperty("isArchived").GetBoolean()));
        }
        return result;
    }

    public static BookingsPage ToBookingsPage(JsonElement data)
    {
        JsonElement page = data.GetProperty("bookingsPage");
        var items = new List<BookingSummary>();
        foreach (JsonElement b in page.GetProperty("items").EnumerateArray())
        {
            bool hasLink = b.TryGetProperty("shareLink", out JsonElement link) && link.ValueKind != JsonValueKind.Null;
            bool hasContact = b.TryGetProperty("guestContact", out JsonElement contact) && contact.ValueKind != JsonValueKind.Null;

            items.Add(new BookingSummary(
                b.GetProperty("id").GetString()!,
                b.GetProperty("propertyId").GetString()!,
                b.GetProperty("checkIn").GetString()!,
                b.GetProperty("checkOut").GetString()!,
                b.GetProperty("status").GetString()!,
                hasLink,
                hasContact));
        }
        return new BookingsPage(items, page.GetProperty("totalCount").GetInt64());
    }

    public static GuestFormStatus ToGuestFormStatus(JsonElement data, string bookingId)
    {
        JsonElement status = data.GetProperty("submissionStatus");
        return new GuestFormStatus(bookingId, status.GetProperty("status").GetString()!);
    }

    public static IReadOnlyList<SesStatusEntry> ToSesStatuses(JsonElement data)
    {
        var result = new List<SesStatusEntry>();
        foreach (JsonElement s in data.GetProperty("sesSubmissionStatuses").EnumerateArray())
        {
            result.Add(new SesStatusEntry(
                s.GetProperty("bookingId").GetString()!,
                s.GetProperty("status").GetString()!,
                s.GetProperty("attempts").GetInt32(),
                GetStringOrNull(s, "lastError"),
                GetStringOrNull(s, "sesReference"),
                GetStringOrNull(s, "loteId"),
                GetStringOrNull(s, "lastAttemptAt")));
        }
        return result;
    }

    public static UsageSummary ToUsageSummary(JsonElement data)
    {
        JsonElement u = data.GetProperty("partelistoUsageInfo");
        JsonElement limits = u.GetProperty("limits");
        return new UsageSummary(
            u.GetProperty("tier").GetString()!,
            u.GetProperty("trialActive").GetBoolean(),
            u.GetProperty("trialDaysRemaining").GetInt32(),
            u.GetProperty("propertiesCreatedThisMonth").GetInt32(),
            limits.GetProperty("maxProperties").GetInt32(),
            u.GetProperty("templatesCreatedThisMonth").GetInt32(),
            limits.GetProperty("maxTemplates").GetInt32(),
            u.GetProperty("bookingsCreatedThisMonth").GetInt32(),
            limits.GetProperty("maxBookingsPerMonth").GetInt32());
    }

    public static SendGuestLinkResult ToSendGuestLinkResult(JsonElement data)
    {
        JsonElement payload = data.GetProperty("sendGuestLink");
        return new SendGuestLinkResult(
            payload.GetProperty("sent").GetBoolean(),
            payload.GetProperty("recipient").GetString()!,
            GetStringOrNull(payload, "error"),
            payload.GetProperty("expiresAt").GetString()!);
    }

    public static IReadOnlyList<TemplateSummary> ToTemplates(JsonElement data)
    {
        var result = new List<TemplateSummary>();
        foreach (JsonElement t in data.GetProperty("templates").EnumerateArray())
        {
            result.Add(new TemplateSummary(
                t.GetProperty("id").GetString()!,
                GetStringOrNull(t, "archivedAt") is not null));
        }
        return result;
    }

    public static BookingCreated ToBookingCreated(JsonElement data)
    {
        JsonElement booking = data.GetProperty("createBooking").GetProperty("booking");
        return new BookingCreated(
            booking.GetProperty("id").GetString()!,
            booking.GetProperty("propertyId").GetString()!,
            booking.GetProperty("templateId").GetString()!,
            booking.GetProperty("checkIn").GetString()!,
            booking.GetProperty("checkOut").GetString()!,
            booking.GetProperty("status").GetString()!);
    }

    private static string? GetStringOrNull(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out JsonElement value) && value.ValueKind != JsonValueKind.Null
            ? value.GetString()
            : null;
}
