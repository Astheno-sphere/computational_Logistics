using System.Text.Json;
using FluentAssertions;
using TargetGrps.Partelisto.Mcp.Application;

namespace TargetGrps.Partelisto.Mcp.UnitTests;

public class ResponseShaperTests
{
    [Fact]
    public void ToProperties_maps_every_field_and_no_more()
    {
        JsonElement data = Parse("""
            {
              "properties": [
                { "id": "p1", "name": "Casa Sol", "address": "Calle 1", "municipality": "Sevilla", "province": "Sevilla", "isArchived": false },
                { "id": "p2", "name": "Casa Luna", "address": "Calle 2", "municipality": null, "province": null, "isArchived": true }
              ]
            }
            """);

        IReadOnlyList<PropertySummary> result = ResponseShaper.ToProperties(data);

        result.Should().BeEquivalentTo(
        [
            new PropertySummary("p1", "Casa Sol", "Calle 1", "Sevilla", "Sevilla", false),
            new PropertySummary("p2", "Casa Luna", "Calle 2", null, null, true)
        ]);
    }

    [Fact]
    public void ToBookingsPage_never_surfaces_guest_email_or_phone_even_if_the_gateway_sent_them()
    {
        // A defense-in-depth check: even if a future edit to GatewayQueries accidentally widened the
        // selection to include email/phone, ResponseShaper must still not read them into the DTO.
        JsonElement data = Parse("""
            {
              "bookingsPage": {
                "totalCount": 1,
                "items": [
                  {
                    "id": "b1", "propertyId": "p1", "checkIn": "2026-09-01", "checkOut": "2026-09-05",
                    "status": "SENT",
                    "shareLink": { "expiresAt": "2026-09-05T12:00:00Z" },
                    "guestContact": { "name": "Ana", "email": "ana@example.com", "phone": "+34600000000" }
                  }
                ]
              }
            }
            """);

        BookingsPage result = ResponseShaper.ToBookingsPage(data);

        result.TotalCount.Should().Be(1);
        BookingSummary booking = result.Items.Single();
        booking.HasCheckinLink.Should().BeTrue();
        booking.HasGuestContact.Should().BeTrue();
        // BookingSummary has no email/phone property at all — this is the actual guarantee: it is not
        // representable, not just unpopulated. The assertion below is a canary that fails to compile,
        // not to run, if that ever changes.
        typeof(BookingSummary).GetProperty("GuestEmail").Should().BeNull();
        typeof(BookingSummary).GetProperty("GuestPhone").Should().BeNull();
    }

    [Fact]
    public void ToBookingsPage_handles_no_link_and_no_contact_yet()
    {
        JsonElement data = Parse("""
            {
              "bookingsPage": {
                "totalCount": 1,
                "items": [
                  { "id": "b1", "propertyId": "p1", "checkIn": "2026-09-01", "checkOut": "2026-09-05", "status": "DRAFT", "shareLink": null, "guestContact": null }
                ]
              }
            }
            """);

        BookingSummary booking = ResponseShaper.ToBookingsPage(data).Items.Single();

        booking.HasCheckinLink.Should().BeFalse();
        booking.HasGuestContact.Should().BeFalse();
    }

    [Fact]
    public void ToGuestFormStatus_maps_status()
    {
        JsonElement data = Parse("""{ "submissionStatus": { "status": "Submitted" } }""");

        GuestFormStatus result = ResponseShaper.ToGuestFormStatus(data, "b1");

        result.Should().Be(new GuestFormStatus("b1", "Submitted"));
    }

    [Fact]
    public void ToSesStatuses_maps_all_entries_with_nulls_preserved()
    {
        JsonElement data = Parse("""
            {
              "sesSubmissionStatuses": [
                { "bookingId": "b1", "status": "Accepted", "attempts": 1, "lastError": null, "sesReference": "REF1", "loteId": "L1", "lastAttemptAt": "2026-08-30T10:00:00Z" },
                { "bookingId": "b2", "status": "Failed", "attempts": 3, "lastError": "timeout", "sesReference": null, "loteId": null, "lastAttemptAt": null }
              ]
            }
            """);

        IReadOnlyList<SesStatusEntry> result = ResponseShaper.ToSesStatuses(data);

        result.Should().BeEquivalentTo(
        [
            new SesStatusEntry("b1", "Accepted", 1, null, "REF1", "L1", "2026-08-30T10:00:00Z"),
            new SesStatusEntry("b2", "Failed", 3, "timeout", null, null, null)
        ]);
    }

    [Fact]
    public void ToUsageSummary_maps_tier_trial_and_limits()
    {
        JsonElement data = Parse("""
            {
              "partelistoUsageInfo": {
                "tier": "free", "trialActive": true, "trialDaysRemaining": 5,
                "propertiesCreatedThisMonth": 2, "templatesCreatedThisMonth": 1, "bookingsCreatedThisMonth": 4,
                "limits": { "maxProperties": 3, "maxTemplates": 2, "maxBookingsPerMonth": 10 }
              }
            }
            """);

        UsageSummary result = ResponseShaper.ToUsageSummary(data);

        result.Should().Be(new UsageSummary("free", true, 5, 2, 3, 1, 2, 4, 10));
    }

    [Fact]
    public void ToSendGuestLinkResult_maps_success_and_failure_shapes()
    {
        JsonElement success = Parse("""
            { "sendGuestLink": { "sent": true, "recipient": "guest@example.com", "error": null, "expiresAt": "2026-09-05T12:00:00Z" } }
            """);
        JsonElement failure = Parse("""
            { "sendGuestLink": { "sent": false, "recipient": "", "error": "Guest email address is not valid.", "expiresAt": "2026-09-05T12:00:00Z" } }
            """);

        ResponseShaper.ToSendGuestLinkResult(success).Sent.Should().BeTrue();
        ResponseShaper.ToSendGuestLinkResult(failure).Error.Should().Be("Guest email address is not valid.");
    }

    [Fact]
    public void ToTemplates_maps_id_and_archived_flag()
    {
        JsonElement data = Parse("""
            {
              "templates": [
                { "id": "t1", "archivedAt": null },
                { "id": "t2", "archivedAt": "2026-01-01T00:00:00Z" }
              ]
            }
            """);

        IReadOnlyList<TemplateSummary> result = ResponseShaper.ToTemplates(data);

        result.Should().BeEquivalentTo(
        [
            new TemplateSummary("t1", false),
            new TemplateSummary("t2", true)
        ]);
    }

    [Fact]
    public void ToBookingCreated_unwraps_the_mutation_payload()
    {
        JsonElement data = Parse("""
            {
              "createBooking": {
                "booking": {
                  "id": "b1", "propertyId": "p1", "templateId": "t1",
                  "checkIn": "2026-09-12", "checkOut": "2026-09-15", "status": "Draft"
                }
              }
            }
            """);

        BookingCreated result = ResponseShaper.ToBookingCreated(data);

        result.Should().Be(new BookingCreated("b1", "p1", "t1", "2026-09-12", "2026-09-15", "Draft"));
    }

    private static JsonElement Parse(string json) => JsonDocument.Parse(json).RootElement.Clone();
}
