# Product Advice for Hardware Founders

**Author:** Eric Migicovsky
**Type:** Essay
**URL:** https://www.ycombinator.com/library/47-product-advice-for-hardware-founders

---

Product Advice for Hardware Founders

# Product Advice for Hardware Founders

by Eric Migicovsky

YC Partner [Eric Migicovsky](https://twitter.com/ericmigi) recently did a Hardware AMA with Startup School founders. It
was so good that we wanted to share it here.

Enjoy!

* * *

**Software is easy to release and sell as a beta, but we're worried it will be hard to sell our hardware if it looks too**
**"prototype-y."**

**How can Hardware startups sell product as early as possible?**

**Are preorders usually required, or is there a way to can sell product before setting up high-volume manufacturing?**

I could help more if you describe what you're working on. But in general, you should try to be as hacky and prototype-y
as possible. I wrote about this here:
[https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/](https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/)

![YC Logo](<Base64-Image-Removed>)

# What is Y Combinator?

We're an accelerator that funds startups — like Coinbase, Instacart, Reddit, Doordash — at their earliest stages. Starting a company? Even if it feels early, 40% of our companies joined with just an idea.

[Apply](https://www.ycombinator.com/apply)

For example:

- Buy off the shelf hardware (eg RasPi + USB camera) and enclose it in a 3D printed case. Sell it. Many YC companies
have done this in the past (eg Flock's first gen device was exactly this -
[flocksafety.com](https://www.flocksafety.com/), and Piccolo)
- Buy a device that already does 90% of what you want it to do, then work with the manufacturer to customize the
last 10% (I explained it a bit in that TC post)

You can sell preorders but I find it easier to simply build 2-3 units then actually sell them to early users. Then use
the profits from that to build more units, sell them, repeat. That's what we did for our first gen watch, inPulse. It
worked great, we manufactured the first 1000 units one-by-one in the garage. Secondary benefit: you can immediately
incorporate improvements into the product as you assemble them. Of the first 20 units we shipped - 4-5 were completely
destroyed during shipping. We fixed that asap and never had the problem again.

**Please tell your top must-read books for Hardware Startup entrepreneurs?**

- [Piloting Palm](https://www.amazon.com/Piloting-Palm-Handspring-Billion-dollar-Handheld/dp/075678798X) is the best,
most accurate book about starting a consumer electronics company. A bit dated, but still highly recommended.

- +1 for [The Hardware Hacker by\\
Bunnie](https://www.amazon.com/Hardware-Hacker-Adventures-Making-Breaking/dp/159327758X).

- Also [Pirates of Silicon Valley](https://www.imdb.com/title/tt0168122/)!


**What tools/resources did you use to develop and manufacture prototype?**

Our first prototype was just an Arduino (atmega) plus a screen from a Nokia 3310 smartphone. See the first proto here:
[https://www.youtube.com/watch?v=qVZDx86Ft0o](https://www.youtube.com/watch?v=qVZDx86Ft0o) For the next gen (called inPulse), we made the watch case out of CNC

Watchduino - YouTube

[Photo image of erOhead](https://www.youtube.com/channel/UClWqxA1WXz5ZZf-9HcCzthQ?embeds_referring_euri=https%3A%2F%2Fwww.ycombinator.com%2F)

erOhead

63 subscribers

[Watchduino](https://www.youtube.com/watch?v=qVZDx86Ft0o)

erOhead

Search

Info

Shopping

Tap to unmute

If playback doesn't begin shortly, try restarting your device.

You're signed out

Videos you watch may be added to the TV's watch history and influence TV recommendations. To avoid this, cancel and sign in to YouTube on your computer.

CancelConfirm

Share

Include playlist

An error occurred while retrieving sharing information. Please try again later.

Watch later

Share

Copy link

Watch on

0:00

/

•Live

•

milled aluminium and designed a custom PCB. We actually manufactured this in our garage and sold several thousand units.

**What did you change in your product after YC W11?**

Biggest feedback we received from inPulse users was: longer battery life (was 24 hours), outdoor readable display, needs
to work with iPhone, support for fitness tracking apps. We took the feedback and incorporated it into the first Pebble
watch

**Would be great if you share your YC Application**

Sure, here it is: [https://drive.google.com/file/d/1CemwTH8UpInp6wqyv822Usu\_PQR\_Ho8s/view?usp=sharing](https://drive.google.com/file/d/1CemwTH8UpInp6wqyv822Usu_PQR_Ho8s/view?usp=sharing)

**How much did you spend on the Kickstarter campaign?**

We spent $5k on prototypes for the first campaign. Borrowed a camera and filmed the video ourselves. No other spend.

**When did you find the market fit, and how did YC and Kickstarter help you and your team with this?**

YC heavily encouraged me to talk to my users more. I had definitely been bad at this before YC. We also moved much
quicker during YC. PG asked why we didn't have an SDK for devs to write apps for inPulse. I gave all kinds of excuses
but eventually he just asked 'how long would it take to write one?'. We said 2 weeks, and he convinced us to just f'n do
it. We did and it turned out to be a critical part of product development that lead us towards Pebble (which reached
product market fit).

**Topic: How to be defensible?**

**I applied for HAX accelerator and they rejected me saying: "Your product is good and innovative but not defensible. It**
**can easily be copied".**

**My product is a completely mechanical wheelchair. How to proceed in this case for being defensible. Anything other**
**than patents that can help me here?**

**As without any electronics/codes/app I can't go for achieving network effects. And being completely mechanical**
**product, anyone can reverse engineer it.**

**There also comes the fear of getting copied by someone in the market (soon if the product starts selling good).**

One thing I've learned about rejections: listen to the 'no' but not the 'why'. Often times investor (including YC) have
no idea whether a company is going to be successful or not, but it's easier to reject than accept. We come up with vague
reasons why we shouldn't fund the company and then move on. From the entrepreneurs side, it's hard to understand because
usually the reasons sound logical but the crazy part is the VC probably will not fund you even if you fix the problems
that they outlined.

Defensibility is my view is the ability to build some sort of moat around your product that either:

a) disincentivizes customers from leaving for a competitor or

b) reduces/eliminates competition. There are many ways to build this into hardware companies:

- strong brand or great customer service
- hw built on a software platform
- access to a better supply chain, or cheaper/faster logistics
- many more...

In your case, I bet the most defensible thing you could do is truly care about your customers base and move quickly to
build products or features that your customers want. While this is not perfectly defensible, you'll be surprised by how
few companies actually do this :)

**Assuming that your MVP is a SaaS that receives feedback from a few devices: what are your thoughts on going to market**
**with a hardware solution where your core piece is a commercial single-board computer (Raspberry Pi Zero W)?**

You are on the perfect track. Do exactly that. I wish more people would follow your exact plan! There is a ton of money
to be made by using off the shelf hardware, writing great software and solving a real business need.

**I build a scripting framework for bash which may have use cases for companies building systems on embedded Linux**
**devices. Where can I find companies or strategic partners that are building hardware/IOT products on embedded Linux?**

I recommend reading about some past attempts in this space. Most recently the $9 computer people (Next Thing Co
[https://en.wikipedia.org/wiki/CHIP\_(computer)](https://en.wikipedia.org/wiki/CHIP_(computer)) tried to do this and it didn't work out. Probably because they were
making customer chips though.

Honestly most hw companies are very resistant to using off the shelf software in their custom builds. Might be an
extreme case of NIH. I am always surprised by few companies there are that make sw libraries or modules specifically for
embedded systems.

You can find potential customers on subreddits for embedded development, or on podcasts like EEVBlog or hackaday.

**We're a hardware startup building an interactive learning robot for kids. In the current funding environment, how much**
**weight do you feel seed stage investors are assigning to a crowdfunding campaign?**

I personally assign a lot more value to a company that has shipped _something_ to paying customers. Doesn't matter how
many units, 1 is a great start! Shipping a product means the founders have:

- developed an idea into an actual solution to a problem
- figured out some basic marketing and found potential customers
- convinced those customers to part with their hard earned cash
- built and manufactured at least one working unit
- figured out the logistics of shipping and doing customer support
- have a happy customer

It's actually a lot cheaper (generally) to do this rather than execute a potentially expensive crowdfunding campaign.
The best companies I've seen actually do the above, sell 50-100 units and then use the knowledge that they've gained
from that process to create a fantastic crowdfunding campaign. They learn what potential customers actually want out of
their product and how to correctly market it.

**As you know, hardware startups are expensive. We are currently raising a SEED round and our ideal funding amount**
**sometimes feels higher than we are comfortable asking for. When you are pitching your MVP product with a small number of**
**users, how do you justify asking for the money required to take your hardware product from MVP to CVP? Especially when a**
**software product can do it for so much less?**

If you are already selling your product, why raise a seed round at all? Why not continue selling units to customers and
grow your business organically off the profits from your sales? Raising money is super distracting from building product
and talking to customers. I would recommend focusing on that.

Hardware startups in general are slightly more expensive that sw startups, but actually not that much more. It does
depend on what you're making of course. We started shipping the first hundred units of the inPulse watch on total spend
of less than $50k CAD in 2010.

**We are also working on prototype of fitness band(Patch). We already released android fitness activity tracker app for**
**the same with few active users.**

**I want to know how to reduce the expenses while building an MVP & how to reach potential customers.**

**Another question is what are the key points we have to consider while designing a hardware product?**

What expenses do you have right now? Presumably not many. Hard to know what to reduce without knowing what you're
currently spending :)

Key points: same as with a software product. Are you building something that people want? This above all is the most
important thing you should be working on. Finding product-market fit. Everything (literally) else is secondary to this
all important goal. Often times HW founders think that cost optimization, or beautiful industrial design, etc etc is
important...at an early stage - it's not. The only thing that truly matters is 'do people want to pay for your product
and do they like using it'

**We are developing a 3Door device using 3D face reconstruction and recognition technology. 3Door will have features**
**like video doorbell, video interphone, security camera and smart access system. In a one-liner, you will be able to**
**unlock the door of your property using your face. We developed algorithm and now we are working on a hardware**
**development. We have a prototype but now we are looking how to make it more `consumer friendly/fancy`.**

**1) Do you have some advice on how to find a vendor for electronics and printed board instead of using Raspberry Pi3 or**
**you think that Pi3 will work well in our case?**

**2) Also about the design of hardware, do you have a suggestion how to find the person that can help us with that task**
**and anything else (advice/suggestions) related to this part will be very helpful for us.**

Cool! I love smart door stuff. I've had a Lockitron on my door since Sept 2011 and haven't carried a key since then :)

1. Sounds like a Pi would be great for your use case. Just 3D print a nice case and make sure it can't be easily stolen
:)

2. which part of the hardware design do you need help with? You could try posting on this forum, another startup may
know someone who could help. For example there are many industrial designers who can do case design remotely


**Are there any resources you could recommend for quality control and do you have any tips for sourcing and working with**
**manufacturers?**

**I have an electronics client and they have ~10% return rate. Last batch they had a 24% return rate supposedly due to**
**a defective batch. How can you tell between defective hardware and bad design? For QC, they have a team in China that**
**checks random x items to determine the defect rate, but is there a way to automate the QC testing process, or more**
**sophisticated and better ways for QC? Or is the only way having someone on the team there at the factory?**

Is this an enterprise (b2b) or consumer product? Each group has different standards. If they are seeing 24% return rate,
they have a big problem. One way to solve this is to institute 100% QC at the factory - meaning one of their team
members, or someone they trust (not a factory working) is in-line at the factory checking each unit as it's prepared.
It's a huge time sink and annoying but sometimes this is the only way to fix problems at the factory.

**Do we need to get validation that the problem we are trying to solve is 'hair on fire'-type before building the MVP?**
**We are building an IOT cushion to correct user posture and increase physical activity. People we to talk so far don't**
**believe it as there is no product to show.**

When looking for potential markets for a product I consider a venn diagram of 3 circles:

- severity of problem (how much money can be earned or saved)
- frequency of problem
- spending power (does the person with the problem have the power to buy a solution)

The best hair on fire problems are people at the centre of all 3 circles. You can test your potential market by talking
to customers and determining how willing they are to spend money to solve their problem. People with 'hair on fire'
problems should be willing to prepay for a solution to their problem.

**Outsourcing Advice: Which part of that hardware startup, one can be better off by getting it done by a third party and**
**not necessarily from a founding team?**

**Which one is preferred: Learning the activity self, and trying it first hand with the higher risk of failure at**
**implementation or outsourcing it to a third party with the risk of beind dependent on outside at cost of some**
**leverage?**

**Things like Supply Chain, Web design, Industrial design, Aesthetics, Legal compliances etc.**

This was a lesson I learned at the beginning of Pebble: it's impossible to pay someone enough to care about your
startup. You and your cofounders are the only ones who actually care. You are the ones who get up in the morning and
throw 110% of your energy into making your vision come true.

In the early days, I thought I could get by with contractors doing things but they invariably failed, charged too much
(and then failed) or did shitty work. The most helpful non-founders were friends of mine who I con(vinc)ed into doing
odd projects, helping with the early assembly line and such. Looking back, I wish I had offered to make them cofounders
and encouraged them to come on full-time.

In the early days, when money is super tight, founders have no choice but to do literally everything themselves. And
that's a good thing. Learning how to do something makes you better at outsourcing it later. Your naivety will also be an
advantage - you may not know that something is 'impossible' and accidentally create a novel solution that an expert may
have written off a long time ago. I benefited from a number of these situations.

The one area that I would recommend cultivating is a network of advisors and startup founders that are a few years ahead
of you in the process. These people are the best sounding boards for questions like 'who should I use for FCC testing'
or 'should I use Shopify or build my own ecommerce site?' (answer: USE SHOPIFY).

**I'd like to know the strategies you used to boost the success of your kickstarter campaign. If you had to do it all**
**over again would you still go for crowdfunding (why/why not)? Thanks for your time.**

People tend to overlook the fact that I started Pebble in 2008, shipped several thousand units of inPulse in 2010-2011
and only launched Pebble on Kickstarter in 2012. That was 5 years later. We learned a ton in those early years, improved
the product and figured out how to market it. That's the real reason why our Kickstarter was so successful in 2012.
There are no silver bullets.

If I were to do it all over again, I would definitely focus on shipping a working albeit alpha product to customers
first, then only after shipping many units of that would I move onto a crowdfunding campaign.

**In your experience, what is the minimum level of fidelity that a seed or an investor wants to see in a prototype/MVP?**
**Any way to know it before pitching? Any recommendation? What was yours?**

**Breaking the chicken and egg is really difficult, and wasting time on useless twitches is a very real problem for a**
**hardware startup. But a fugly MVP seems to get you nowhere...**

As a seed investor, I look first to see if the startup has shipped product to a paid customer. That's the gold standard

- if you can do that, you're ahead of 99% of all other hw startups. So try to do that - don't build a prototype just to
impress investors.

A fugly MVP with paying customers is no longer a prototype...it's a real damn product with a market!

**I and my friend are both web developers. Recently, we're so passionate about the idea of autonomous robot charging. We**
**know that it involves high technology of AI and Robotic, but we believe in the vision and so start learning AI and**
**Self-driving, which has a lot of similarity to our idea in tech aspect. We really want to bring in another cofounder who**
**has decent knowledge in tech.**

**How do you bring in cofounders or hire technical people in these highly expertised engineering field?**

**Since the learning curve is super steep, should we keep learning until we build a prototype to be more easily pitch in**
**a new cofounder or go networking right the way, by just pitching the concept to try to bring in a new cofounder?**

Since you both are already technical, you could consider researching and studying the technology and work to build it
yourself. I'd recommend this route as it's entirely within your control - you don't rely on any outside forces to make
it happen. Alternatively you could consider bringing on another cofounder, especially if you happen to have a friend or
past colleague in the space! But oftentimes I find that technical and problem solving ability beats experience in a
particular domain.

**I'm a software engineer. I have 2 hardware product ideas but I don't have the expertise on electronic/electrical**
**field. What are the good ways I can find a like minded hardware expert as co-founder to research and bring out a**
**product?**

Sounds cool! What are the product ideas? Best way is to start by sharing your ideas with practically every person you
meet. You never know who will be a) interested in the same stuff and b) have a complementary skill set that can help you
make it a reality.

**The key problem that I have right now is a manufacturing management. We got 6 months delay at the first batch and 4**
**months delay on the second production batch. Yes, we are still alive but I'm looking for a new manufacturer. I'm afraid**
**that the problem is not in manufacturer but in my incompetence​ in managing them.**

**QUESTION: Is there a proper way to deal (manage) with suppliers and manufacturers to get the product on time and with**
**the expected quality?**

**I know that we can set strict terms in a written contract/agreement, to cover the risks, but the manufacturer**
**increases the price and increase the lead-time. Also, because the manufacturing cost is 2x-3x lower than the MSRP, I**
**can’t assign the direct delay losses to the manufacturer as an equation MSRP \* PO Quantity = Fines.**

We had the same type of problems with Pebble - long lead time components really constrained us. If I were to do it
again, I will try to design products specifically with easier to source components.

Have you traveled to visit your supplier in person? Sometimes it takes in-person pressure to kick people into gear.
Contracts will never have the right effect, they have to sense that you care and will stop at nothing to get it done. So
it might be time to get on a plane and camp out at the factory until they get moving.

**Do you have any advice on pitfalls hardware startups should avoid as they mature? I'm not sure if it's a subject you**
**want to broach as Pebble had a large sales success but was sold to Fitbit. There are also a lot of consumer electronics**
**companies that do IPO but struggle to maintain financial success afterwards (notable exceptions exist).**

**I just would like an idea of what to expect on the road ahead of a hardware startup after prototyping, manufacturing,**
**and sales no longer become issues to contend with. Much thanks!**

Really depends on the type of company. Consumer or enterprise? One-time sale or recurring subscription? The best advice
for early stage companies is 'how not to fail' by Jessica Livingston [https://blog.ycombinator.com/how-not-to-fail/](https://blog.ycombinator.com/how-not-to-fail/) and
'how not to die' by PG [http://www.paulgraham.com/die.html](http://www.paulgraham.com/die.html)

Hardware startups usually die for the same proximate cause as non HW cos: they run out of money. It's exacerbated for HW
startups because they have inventory which locks of their cash early in the sales cycle. If I were to recommend one
thing for hw startups - understand your cash conversion cycle and make sure you have the right 'business model to
company' fit, which is just as important as PMF for hw companies.

**My question is about the ethics of manufacture: Do you have any insights on how we could be more mindful of product**
**impact on a long term basis?, the possible impact it could have on the planet, the ethics of the suppliers &**
**manufacturing processes and long term repercussions, are there any tangible ways (you may have found) to measure or**
**calculate the future impact of a product so it can be negated right at design stage? any resources would be very useful,**
**as it is my goal to make my company among the most ethical on this planet.**

Modern design thinking is centered around something called 'cradle to grave' product design. So you consider the
materials going into your product and how the user will deal with the product after it's lifespan is up. The easiest way
to build this into your product is to design it to last and to be repairable. Then the user can continue to use it long
into the future.

**What's the best way to outsource embedded electronics prototyping? Also, what resources do you recommend when looking**
**for a manufacturing partner in China?**

I wrote a post precisely about this:
[https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/](https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/)

**It seems to be a catch-22 situation for a new company, as protecting product IP internationally, including design**
**patents, brand IP etc, is cost-prohibitive at an early stage, yet without these in place, launching a product puts the**
**founders in a non defensible position. How would you recommend tackling this challenge especially when your focus is**
**creating a strong international 'Brand image'?**

I would not worry about IP in the early stage except for a very specific set of products (mainly pharmaceuticals). If
you really care about patents then file a super broad provisional patent for $500 to $1000. This gives you 1 year period
to file a full patent for anything that you actually end up building.

"Don't worry about people stealing your ideas. If your ideas are any good, you'll have to ram them down people's
throats."

**My company is working on remote control cars for car sharing companies. We’re remotely piloting cars so that there’s**
**no need for an in car driver. Right now we are in the very early stages of development but we had a few questions.**

**1\. Our team eventually will need to recruit someone with a mechanical engineering background as my co-founder and I**
**are a bit weak in that department, but we’ve been debating on if that person should be an early hire or a founder. Do**
**you have any advice on how we should evaluate that distinction?**

**2\. Right now we’re bootstrapping development and we believe we have enough savings to get to an MVP though it might be**
**cutting it close. Is there an ideal time to start the fundraising process?**

1. Essentially the first 4-5 people at any company are cofounders. Sometimes they have the title, sometimes not. But
they effectively are and should be treated as such with large amounts of equity. Think of it this way - if the
first 4-5 people aren't spending every waking second thinking about how to make the company a success, who else is
going to? If you are relying on them to do this, they should be compensated as such. Some people need to make more
money for personal reasons, that's okay but the important thing is they still have a large % of equity. Don't be
stingy with equity to someone who is putting in 20% of the effort to make your company a raging success.

2. No, fundraising basically always sucks. I would try to optimize for earning revenue over trying to time fundraising.
If you earn revenue you have cash to fund further growth and the happy side effect of making investors want to
invest in you!


**1\. How essential is it to figure out the manufacturing aspect very early on versus just making an MVP prototype as**
**soon as you can?**

**2\. Where can we go to read/learn about hardware startups and their product-market-fit process, and especially, how**
**they scaled effectively? (including Pebble)**

1. Speed speed speed! The one thing a startup needs to accomplish is prove that they have product market fit.
Everything else is secondary. So make the MVP asap!

2. This is a great blog by a friend of mine. Fellow HW founder: [http://marcbarros.com/](http://marcbarros.com/)


**What is your opinion in engaging product design companies if we can't build the complete hardware all by ourselves?**
**What are the documents needed to protect our IP?**

First I would try to build it all yourselves without working with product design companies. Not because of IP, but
because they'll bleed you dry with fees and are generally slow. Now I don't know what you're trying to build (feel free
to share!) but in general, I'd recommend pursuing a path more like this:
[https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/](https://techcrunch.com/2017/09/19/what-working-on-pebble-taught-me-about-building-hardware/)
