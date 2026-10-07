using System.Reflection;
using FluentAssertions;
using TargetGrps.Partelisto.Mcp.Application;

namespace TargetGrps.Partelisto.Mcp.UnitTests;

/// <summary>
/// A cheap static guard, not a functional test: fails the build the moment a GraphQL document in
/// GatewayQueries selects a field that could carry guest personal data, so a well-meaning "let's also
/// return the guest's email while we're at it" edit gets caught in review, not in production.
/// </summary>
public class GatewayQueriesTests
{
    private static readonly string[] ForbiddenFieldNames =
    [
        "email", "phone", "dni", "passport", "documentnumber", "dateofbirth", "birthdate",
        "nationality", "documentpdf", "documentcsv", "signature", "address2"
    ];

    [Fact]
    public void No_query_selects_a_field_name_that_could_carry_guest_personal_data()
    {
        foreach (FieldInfo field in typeof(GatewayQueries).GetFields(BindingFlags.Public | BindingFlags.Static))
        {
            string query = (string)field.GetValue(null)!;
            string lowered = query.ToLowerInvariant();

            foreach (string forbidden in ForbiddenFieldNames)
            {
                lowered.Should().NotContain(forbidden,
                    $"GatewayQueries.{field.Name} must not select a field resembling guest PII ('{forbidden}')");
            }
        }
    }
}
