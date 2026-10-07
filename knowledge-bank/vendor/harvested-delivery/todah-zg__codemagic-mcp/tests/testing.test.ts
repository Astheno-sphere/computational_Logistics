import { describe, it, expect } from "vitest";
import { parseJUnitXml } from "../src/testing.js";

const ALL_PASS = `
<testsuites>
  <testsuite name="SuiteA" tests="3" failures="0" errors="0" skipped="0" time="1.5">
    <testcase name="testFoo" classname="com.example.Foo" time="0.3"/>
    <testcase name="testBar" classname="com.example.Foo" time="0.5"/>
    <testcase name="testBaz" classname="com.example.Foo" time="0.7"/>
  </testsuite>
</testsuites>
`.trim();

const WITH_FAILURE = `
<testsuites>
  <testsuite name="SuiteB" tests="3" failures="1" errors="0" skipped="1" time="2.1">
    <testcase name="testPass" classname="com.example.Bar" time="0.4"/>
    <testcase name="testFail" classname="com.example.Bar" time="0.6">
      <failure message="Expected 1 but was 2" type="junit.framework.AssertionError">
        at com.example.Bar.testFail(Bar.java:42)
      </failure>
    </testcase>
    <testcase name="testSkip" classname="com.example.Bar" time="0.0">
      <skipped/>
    </testcase>
  </testsuite>
</testsuites>
`.trim();

const WITH_ERROR = `
<testsuite name="SuiteC" tests="2" failures="0" errors="1" skipped="0" time="0.8">
  <testcase name="testOk" classname="SomeTest" time="0.3"/>
  <testcase name="testCrash" classname="SomeTest" time="0.5">
    <error message="NullPointerException" type="java.lang.NullPointerException">
      at SomeTest.testCrash(SomeTest.java:10)
    </error>
  </testcase>
</testsuite>
`.trim();

const MULTI_SUITE = `
<testsuites>
  <testsuite name="Suite1" tests="2" failures="0" errors="0" skipped="0" time="1.0">
    <testcase name="t1" classname="A" time="0.5"/>
    <testcase name="t2" classname="A" time="0.5"/>
  </testsuite>
  <testsuite name="Suite2" tests="2" failures="1" errors="0" skipped="0" time="1.2">
    <testcase name="t3" classname="B" time="0.5"/>
    <testcase name="t4" classname="B" time="0.7">
      <failure message="oops" type="AssertionError">detail</failure>
    </testcase>
  </testsuite>
</testsuites>
`.trim();

describe("parseJUnitXml", () => {
  it("parses an all-passing suite", () => {
    const r = parseJUnitXml(ALL_PASS);
    expect(r.totalTests).toBe(3);
    expect(r.passed).toBe(3);
    expect(r.failed).toBe(0);
    expect(r.errors).toBe(0);
    expect(r.skipped).toBe(0);
    expect(r.failedCases).toHaveLength(0);
    expect(r.suites).toHaveLength(1);
    expect(r.suites[0].name).toBe("SuiteA");
  });

  it("parses a suite with a failure and a skip", () => {
    const r = parseJUnitXml(WITH_FAILURE);
    expect(r.totalTests).toBe(3);
    expect(r.passed).toBe(1);
    expect(r.failed).toBe(1);
    expect(r.skipped).toBe(1);
    expect(r.failedCases).toHaveLength(1);
    const f = r.failedCases[0];
    expect(f.name).toBe("testFail");
    expect(f.status).toBe("failed");
    expect(f.failureMessage).toBe("Expected 1 but was 2");
    expect(f.failureType).toBe("junit.framework.AssertionError");
    expect(f.failureDetail).toContain("Bar.java:42");
  });

  it("parses a bare <testsuite> root (no <testsuites> wrapper)", () => {
    const r = parseJUnitXml(WITH_ERROR);
    expect(r.totalTests).toBe(2);
    expect(r.errors).toBe(1);
    expect(r.failedCases).toHaveLength(1);
    expect(r.failedCases[0].status).toBe("error");
    expect(r.failedCases[0].failureMessage).toBe("NullPointerException");
  });

  it("merges counts across multiple suites", () => {
    const r = parseJUnitXml(MULTI_SUITE);
    expect(r.suites).toHaveLength(2);
    expect(r.totalTests).toBe(4);
    expect(r.passed).toBe(3);
    expect(r.failed).toBe(1);
    expect(r.failedCases[0].name).toBe("t4");
  });

  it("returns empty results for XML with no testcase elements", () => {
    const r = parseJUnitXml("<testsuites/>");
    expect(r.totalTests).toBe(0);
    expect(r.failedCases).toHaveLength(0);
  });
});
