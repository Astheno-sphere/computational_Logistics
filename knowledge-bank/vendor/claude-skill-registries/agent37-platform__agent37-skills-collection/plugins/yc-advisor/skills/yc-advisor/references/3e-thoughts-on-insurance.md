# Thoughts on Insurance

**Author:** Aaron Harris
**Type:** Essay
**URL:** https://www.ycombinator.com/library/3e-thoughts-on-insurance

---

Table of Contents

[**Table of Contents**](https://www.ycombinator.com/library/3e-thoughts-on-insurance#)

[- Problems](https://www.ycombinator.com/library/3e-thoughts-on-insurance#problems)

[- Opportunities](https://www.ycombinator.com/library/3e-thoughts-on-insurance#opportunities)

[- Misconceptions](https://www.ycombinator.com/library/3e-thoughts-on-insurance#misconceptions)

Thoughts on Insurance

# Thoughts on Insurance

by Aaron Harris

Two years ago, I printed up Chubb's 10k and started reading.[1](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote1) I'd
become interested in the property and casualty insurance industry through a number of conversations with my
father-in-law, who is a commercial broker. While I'd thought a bit about health insurance before that, it was mostly in
the context of my own access to it, and the never-ending debate around Obamacare.

As I read Chubb's financials, industry reports, Warren Buffet's letters, and various blogs I came to realize that the
insurance industry was both far more complex and rife with opportunity than I'd assumed. While I've always been
attracted to fractured and regulated markets, nothing quite mimics insurance in its scope, nuance, and size. I wasn't
the only person thinking about this, as the number of recent insurance tech companies indicates.

## Problems

Here are a few core problems built into the structure of insurance
today.[2](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote2)

**Data** Insurance is fundamentally a data problem. Insurance carriers set their rates based on actuarial models
designed to predict the likelihood of future events. Without access to oracular powers, these models rely on the best
available data when they are built and as they are updated.

This data is necessarily incomplete. It only becomes more incomplete as time goes on and more events pile up in a very
large and unordered world. For instance, a home insurer would be able to better predict the likelihood of fire if it
knew the details of every overloaded power strip in every home in its portfolio. It does not.

![YC Logo](<Base64-Image-Removed>)

# What is Y Combinator?

We're an accelerator that funds startups — like Coinbase, Instacart, Reddit, Doordash — at their earliest stages. Starting a company? Even if it feels early, 40% of our companies joined with just an idea.

[Apply](https://www.ycombinator.com/apply)

The issues faced by carriers with data extends to the setup of carrier/broker relationships. These relationships
necessarily involve lots of paper because there are few simple systems that easily integrate the two sides. This means
that information about customers is often relayed poorly, misunderstood, or simply ignored.

**Structures** Trying to figure out all of the different players in the industry is difficult at best.

When it comes to the distribution side, I can't do it any better than Kyle did here:
[https://medium.com/@kylenakatsuji/so-your-startup-wants-to-sell-insurance-a0167581f7b1](https://medium.com/@kylenakatsuji/so-your-startup-wants-to-sell-insurance-a0167581f7b1).

However, there are even more players involved behind the scenes which are important to understand if you want to uncover
opportunities:

_Reinsurer_ \- There are companies that purchase insurance risk from carriers. They are critical to the system because
insurers will often find that they are overexposed to a given risk (like that presented by hurricanes in the Gulf Coast)
and will need to offload some of that risk. Reinsurers traditionally purchase risk from carriers and from other
reinsurers. Reinsurers have also begun expanding the types of risk that they will purchase and the stage at which
they'll do it, sometimes acting nearly identically to carriers.

_ILS buyers_ \- ILS are Insurance Linked Securities. The most of famous of these are CAT (catastrophe) bonds. These are
created by insurers and reinsurers who wish to syndicate risk beyond the insurance world. This is done by creating a
bond which pays an interest rate and defaults in the case of particular event. The market for these is currently fairly
small, and the bonds are generally purchased by hedge funds. This market will likely expand over time as capital
continues to look for yield.

_Fronting carriers_ \- These are carriers that form partnerships with other entities, like MGAs (Managing General Agent,
defined in Kyle's post above), wherein the MGA writes risk using the regulatory framework of the fronting carrier, and
then immediately sells the risk to a third party. This structure allows entities that could not otherwise sell insurance

- whether through business choice, lack of regulatory capital, or lack of expertise necessary to form a carrier - do so
as long as the fronting carrier agrees.

Fronting carriers are not capitalized in the same way that large carriers are, as they don't hold risk on their own
books. They generally collect a fee - for the use of the regulatory framework - from the entity finding and pricing
risk.

The complexity of the structure of the Insurance market creates 3 other problems, below:

**Value chain** Each of the players in the structure needs to get paid. Premiums are the primary source of revenue
moving into the system, which means that every dollar paid in by customers has to be split between all of the value
providers. After paying for broker commissions, fronting costs, reinsurance, customer service, claims processing,
there's often around 50% of the original premium dollar left to pay claims - which is the primary purpose of an
insurance company.

Splitting a dollar in this many directions means that the individual players need to cut costs as much as possible,
which usually means worse service for customers.

**Fragmentation** Insurance carriers are fragmented at the highest level because of jurisdictional (state or country)
differences in regulations. This often requires different approaches in different markets. Insurance carriers usually
start in one geography with a few core lines and then expand coverage along both measures as they grow. Over time this
means that you have multiple companies offering similar products in similar areas.

The same thing happens to the ecosystem around each carrier such that there's no natural limit to the number of entities
operating in a given market.

**Confusion** The idea of insurance is complicated to begin with. The way it's operated at scale is even more
complicated, and only well understood by people who spend their lives doing it. Consumers generally purchase insurance
when they're forced to (home, auto, health) or guilted into doing so (life insurance). The only other time they interact
with their insurance is when filing a claim, which is usually at a time of huge stress and time pressure. At that point,
they usually deal with a customer service team that's been cut to a bare minimum because of the value chain problem.
This is a terrible dynamic that results in confusion, anger, and massive miscommunication.

**Incentives** The insurance industry is built on mitigating downside risk. Any new thing that they want to do comes
with a thicket of regulatory requirements and considerations. Combine this with the large size of existing players, and
you get a reinforced [innovator's dilemma](https://en.wikipedia.org/wiki/The_Innovator%27s_Dilemma). Notwithstanding the
fact that there are clear benefits to being the first to do certain things - Progressive dominated the first wave of
online acquisition and built a big company as a result - the downsides of a failed new thing are more immediately felt
and painful.

There's also a regulatory requirement in insurance that forces carriers to publicly file new policies. That allows
competitors to copy most of the mechanics and terms for a new
product.[3](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote3) While carriers don't have to file their exact pricing
mechanisms - which will often determine if a product succeeds or fails - knowing that anything successful will soon have
very similar competitors which will learn from your mistakes and then drive up acquisition costs creates a disincentive
to being the first to offer something.

**Differentiation** To the consumer, nearly every player at a given level of the structure looks the same because they
rarely offer unique features or functions. Most carriers are represented by multiple brokers, who generally represent
multiple carriers. This means that businesses have to fight one another on acquisition spend and brand building rather
than meaningful product differentiation. This leads to higher costs and lower margins.

**Speed** Insurance companies are slow. This is true of carriers and of brokers (on balance). Information still moves
back and forth across the system via paper and pdfs. There are multiple players involved in almost every transaction,
and the risk of getting something wrong typically outweighs the goodness that results from faster service.

Auto is a bit different because of a) the similarity of risk and b) the presence of vertically integrated players like
GEICO who have made speed a critical selling point and pulled the market with
them.[4](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote4)

## Opportunities

Given these problems, there are a lot of places to build startups. Here are a few thoughts I've had, and areas I'd like
to see startups attacking.

**Commercial P&C (Property and Casualty) Carrier** This is something I've spent a lot of time thinking about. The way
that insurance for businesses is priced and sold is based on a paper world with little technology, or where technology
is ancillary to the core business of the company.

Increasingly, companies store information in programmatically accessible ways. This means that if you had clever ways to
ingest information about those businesses, you could price their risk more accurately, more frequently, and more
transparently.

A good place to start this business is with startups. They're small customers, but are not particularly well served by
the market. They also grow quickly, so capturing a large portion of them will lead to big customers over time.

**Commercial P&C Broker/MGA** This is similar to the carrier idea, but without the regulations or regulatory capital
requirements which create a barrier to rapid scale. Brokers (or MGAs) can also produce more leverage from their own
technology use than carriers because their revenues are more sensitive to better operations than are a
carrier's.[5](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote5)

However, by moving away from being a carrier, this model loses control over the policies it would issue. I don't
actually think this is a big problem, at least at the start, since existing ISO policies are good enough as a
start.[6](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote6)

**Personal Cyber Insurance** Something I've only recently started thinking about. Most personal cyber insurance is built
around identity theft. While this is certainly a problem, it ignores the extent to which things like ransomware can
disrupt someone's life. Policies that cover these things are usually reserved for high net worth individuals, but that
seems short-sighted.

As more things in our lives become hackable, we'll need more help protecting ourselves from those things. Existing
companies that focus on homeowner's insurance are unlikely to understand these issues well enough to create great
products.

**Auto for autonomous vehicles** Judging from conversations, this is very much on the minds of the existing auto
insurance players. It's unclear who will hold the risk for autonomous driving, or how to structure the related insurance
policies. There are solutions to be built here both on the policy/product side, on the monitoring and claims side, and
probably within the distribution and sales channels.

**Insurance policies as code** It's strange to me that the core of insurance - the policies sold by carriers and
purchased by consumers - are virtually impossible to understand for most consumers. They're a mess of riders,
subclauses, and references to other documents. While policy owners generally know the headlines of any major policy
(generally the amount of coverage they're purchasing and the price), the specifics of coverage are opaque.

This seems like the root of the belief that insurance is an adversarial contest between insurer and insured, which plays
out in contentious claims processes and disgruntled customers. The carriers see the structure as necessary to cover
their own asses, and the customers feel compelled to purchase because they lack other options.

In reality, the policy is a system of nested if/then statements and is well suited to being expressed in code and
exposed to customers as a simulation. This would allow customers to explicitly model various scenarios to learn about
what they'd be covered for, and what would fall outside the bounds of coverage. It would also function as a transparent
tool for claims agents at carriers to show a customer why/why not a given event is covered.

Initially, this might just seem like a nice to have, but done properly this can either be the basis of a much simpler
way to sell (and upsell) insurance, or the core of an industry standard software suite designed to make insurance
companies competitive on customer experience. Implemented properly and at scale, it would even give carriers a way to
rapidly assess the risk of certain events, sell off risk that met certain criteria, and design products to fill the now
apparent holes in their offerings.

## Misconceptions

**Insurance people = dumb** The largest misconception I've seen in insurance startups is the assumption that people
working in the insurance industry are either bad at their jobs or dumb. I've written about this before as [a general\\
case](http://www.aaronkharris.com/presumption-of-stupitidy), but it seems to happen an awful lot in insurance. It's also
flat out wrong. If you spend time talking to actuaries or others within carriers, you'll find a group of smart people
trying to solve hard problems.

Also, there's Warren Buffett.[7](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnote7)

Founders I've met with this view have usually grafted the systemic issues of the insurance system onto individual actors
within it. While the result is the same, understanding the difference means that you can build businesses around
convincing players in the system to act differently so long as you can navigate the systemic issues.

**Carriers = the hard part** When I first started looking at insurance, I quickly gravitated to the idea of spinning up
a new carrier for a number of the problems I noticed. I did this for three reasons:

1. Carriers have control over the largest number of pieces in the insurance space.
2. Carriers can invest their float. I like investing, and I like the idea of having billions of dollars to put to work.
3. Carriers are hard to set up because of the capital required and the complexity of the regulatory structures
involved.

1 is right. 2 is accurate, but it turns out that investing float and earning a company level return off of it is much
harder than it initially appears given the size of float pools and the current low interest rate world. 3 was a very
important red herring.

It turns out that when you talk to experienced insurance people, they don't think of setting up a new carrier as
particularly difficult, just time/resource consuming. For most of the insurance world, the hardest and most important
thing to find is effective distribution and customer acquisition. By focusing on the carrier I was focusing on the
problem I thought existed within insurance, not the actual source of (initial) value that needed to be created. As I dug
deeper, I realized that much (though not all) of what needs to be done to make insurance better for consumers can be
done from a level or three removed from the carrier.

That's good news for startups, because insurance brokers and MGAs can generally move faster and operate at higher
margins than do carriers. They can also focus on one single thing: acquiring customers rather than spending an
inordinate amount time and energy on regulatory issues.

**Complex = impossible** Starting an insurance business is daunting. The complexity is a significant barrier, but it's
also a significant moat for the startups that manage to get over it. One thing that founders and investors need to
realize when investing in the space is that the time scale is likely different than that of companies in other spaces.

Startups that do manage to build the necessary expertise to create new insurance companies, combined with investors
patient enough to wait and support the time needed to do so, will create category-defining companies. The insurance
industry is too large and built on systems too old for any outcome other than massive change.

_Thanks to Jared Friedman, Craig Cannon, and Nick Shalek for reading this over and making it better._

**Notes**

**1.** Here's the most recent one:
[http://s1.q4cdn.com/677769242/files/doc\\\_financials/2016/Q4/Chubb-Limited-2016-Form-10-K.pdf](http://s1.q4cdn.com/677769242/files/doc%5C_financials/2016/Q4/Chubb-Limited-2016-Form-10-K.pdf) [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid1)

**2.** I'm limiting myself to the property and casualty market. Health is a whole different kind of
mess that I haven't spent nearly as much time researching. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid2)

**3.** Because carriers have to publicly file any product they offer with the state, other carriers
can easily offer the same. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid3)

**4.** GEICO is a carrier that owns its own brokers, so information can move through it much more
easily. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid4)

**5.** Carrier revenue is almost entirely determined by whether or not they generate an underwriting
profit/loss and by returns generated on float. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid5)

**6.** ISO ( [http://www.verisk.com/iso.html](http://www.verisk.com/iso.html)) is a subsidiary of a larger company called Verisk that
provides information about insurance risk and other technical services for carriers. ISO has a repository of standard
policies and pricing tools that cover a broad range of risks and can be quickly reused by carriers. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid6)

**7.** Berkshire Hathaway is an insurance company that uses its float to purchase other
companies. [↩](https://www.ycombinator.com/library/3e-thoughts-on-insurance#footnoteid7)
