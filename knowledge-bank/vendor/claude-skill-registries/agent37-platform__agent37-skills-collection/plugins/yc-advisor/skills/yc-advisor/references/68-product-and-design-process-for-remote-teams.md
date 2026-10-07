# Product and design process for remote teams

**Author:** Mike Knoop
**Type:** Video
**URL:** https://www.ycombinator.com/library/68-product-and-design-process-for-remote-teams
**YouTube ID:** zF84IMiSP7I

---

[Mike Knoop](https://twitter.com/mikeknoop) is cofounder and Chief Product Officer at [Zapier](https://zapier.com),
which was in the YC Summer 2012 batch. Zapier moves information between your web apps automatically.

[Kevin Hale](https://twitter.com/ilikevests) is a Visiting Partner at YC. Before YC Kevin was the cofounder of Wufoo,
which was funded by YC in 2006 and acquired by SurveyMonkey in 2011.

You can find Mike on Twitter at [@mikeknoop](https://twitter.com/mikeknoop) and Kevin at
[@ilikevests](https://twitter.com/ilikevests).

-----

## Transcript

Craig Cannon \[00:00:00\] - Hey, how's it going? This is Craig Cannon and you're listening to Y Combinator's Podcast.
Today's episode is with Mike Knoop and Kevin Hale. Mike is Co-founder and Chief Product Officer at Zapier, which was in
the YC Summer 2012 batch. Zapier moves information between your web apps automatically. Kevin's a visiting partner of
YC. Before YC, Kevin was a Co-founder of Wufoo, which was funded by YC in 2006 and acquired by Survey Monkey in 2011.
You can find Mike on Twitter [@MikeKnoop](https://twitter.com/MikeKnoop) and Kevin
[@ilikevests](https://twitter.com/ilikevests). Alright here we go. Hey guys welcome to the podcast. How's it going?

Kevin Hale \[00:00:35\] - Great.

Craig Cannon \[00:00:36\] - Cool. Kevin welcome back. For people who don't know you, what do you do?

Kevin Hale \[00:00:42\] - I'm a partner at Y Combinator. I founded a company called Wufoo back in 2006. I was in the
second batch at YC. That company appropriately was a no office company. We were all remote all the way back then.

Craig Cannon \[00:00:59\] - Huh, that's relevant to today isn't it?

Mike Knoop \[00:01:01\] - Some early inspiration.

Kevin Hale \[00:01:03\] - Wow, what are the odds? Alright Mike so what do you do?

Mike Knoop \[00:01:05\] - Yeah, hi I'm Mike. I am Co-founder at Zapier, I'm their Chief Products Officer. I originally
started out as a front end engineer, a product designer. So I have a very deep appreciation for those areas. I think has
kind of, how I came to run some of the design team today. I've thought a lot about scaling designs teams over the last
seven or eight years.

Craig Cannon \[00:01:25\] - And what does Zapier do?

Mike Knoop \[00:01:26\] - Zapier is a piece of software that helps you automate your tasks at work. Helps you be more
productive. So if you have, if you use multiple tools for your job and you're trying to, you manually copy and pasting
data from one tool to the other all day as part of a task you do, you can use Zapier to automate that and have it done
automatically in the background. So an example would be like if you are a, let's say a project manager and you've got a
team that works out of GitHub and you wanted to send some notifications into Slack or into Jira whenever those issues
get closed you can set that up. Just as one example.

Craig Cannon \[00:02:00\] - Cool, and how did you guys meet? Cause you've known each other for a while.

Mike Knoop \[00:02:03\] - Kevin and I?

Kevin Hale \[00:02:04\] - I came over to the place that you guys were working when you were doing YC and we just talked
for a couple hours. It was a really interesting conversation. Basically I told you, this is what we did at Wufoo. You
should basically just do kind of a lot of the same things. Think about remote work that you're going to be doing this
for a really long time and then, integrations was kind of like patching a bunch of things together to a form builder was
a feature at Wufoo, but to me I saw what they were doing was turning that into an actual business. A lot of my insights
were this is what worked for us. It's really powerful. I totally get why every other company would kind of be interested
in Zapier.

Mike Knoop \[00:02:47\] - You're definitely one of the people who saw early the vision of what Zapier could be in form
software. Such a good use case because the data never ends in a form. You want to do something with it. Usually it's
once someone submits a form I want to go put it in my CRM, or qualify that lead, or put them in an email list somewhere.

Kevin Hale \[00:03:04\] - Its actually interesting that the life cycle of people getting their business online, is you
start of with I need a presence. It's how do I get myself out there? And so use website builders like by default to
become really big. We didn't realize this when we started but we understood this later on. Then people need to figure
out how do I collect data from all these people that are coming to us? And so form building, contact forms, etc. All of
that became really relevant in surveys. And then the next thing is, oh now I have all this new data what do I do with
it? Zapier is the next step. So these are the three stages of every company, oh this is what I need? They have just
giant markets. I remember early days at Wufoo, people had talked to us about, so what's your TAM, what's like your Total
Addressable Market. We literally were just I'm not doing that because it'd be we are, everyone that ever has a web site.
Everyone needs to collect data, like do you want me to calculate that? I've no idea.

Mike Knoop \[00:03:58\] - I sometimes think this exercise is well useful or sometimes a little misleading.

Kevin Hale \[00:04:04\] - It's misleading when your market is so ridiculously large.

Mike Knoop \[00:04:07\] - Yeah, when you're thinking about consumer adoption, you don't ask Facebook what's your TAM.
For us when we think about this opportunity, certainly when we got started our ambitions were, "Hey, can we build a cool
piece of software and support ourselves." But over the over the years I think we realized whoa, we've tapped into
something that almost every person who uses apps and software to get their job done should be using something like
Zapier. There's this explosion in SaaS software in the industry that is, the barrier to entry to creating software is so
low and distributing software is so low, that you get these niche tools and more folks are using these new tools and
bringing them into the workplace. So something almost out of necessity has to exist like Zapier in order to be able to
make those tools play well together. A lot of times, just because of the dynamics of the explosion and how many tools
are, there's no one player in that marketplace that's going to be incentivized to go build thousands of integrations
with everyone else.

Craig Cannon \[00:05:03\] - Yeah I mean at this point surely you do have to be thinking more specifically about personas
and growing out individual markets, right? So how do you approach it now that you have so many users.

Mike Knoop \[00:05:12\] - Yeah, honestly to date it's still the very horizontal strategy. We have mostly focused over
the last seven years about getting more and more apps on Zapier and getting the tools people want on Zapier. I think
that's been one of the things that actually surprised me was how much growth we've been able to get out of the initial,
I guess decision back in 2012 to build an open platform. Looking back that was definitely one of the better decisions I
think we've made in the early days. We built the first 50 or 60 apps on Zapier ourself, Bryan, Wade and I just to
bootstrap that engine and when we launched in 2012, I remember we had live chat, I think a luck on the site at the time
and we got, literally we launched the Tech Crunch and had three days straight where all the chat messages were answering
wishes that people asking for apps that we didn't support and I had never even heard of. It opened my eyes and opened I
think all of our eyes that if we're going to get this thing to scale, we have to figure out a way to get those apps on
Zapier and we just can't do it with three people. So we, it was almost out of necessity. We don't have money to hire. We
can't build these ourselves. So we have to get, figure out a way that partners can build those things on Zapier. And at
that point we had enough inertia momentum from the launch and from early users that were really excited about the
product and that carried us.

Kevin Hale \[00:06:24\] - How do you jumpstart that? Because I think that's like everyone, especially I remember back
then people were talking about the platform. You're going to be a platform, how can you be like Salesforce? The thing is
jump starting that is difficult, just because you put up an API and tell people like hey, if you go and do this, then
you're going to get benefit how did you guys in the early days get people to program against your thing so that I can be
part of your ecosystem when it was very small?

Mike Knoop \[00:06:51\] - It is interesting how every SaaS company, every software company eventually gets big enough,
you want to be a platform. I think I'd always, I'd heard the heuristic of once you get big enough where you could carve
off 1% of your revenue and that could be its own standalone business, you've kind of reached a critical mass that you
could actually build a platform that has legs and can sustain itself. For us in the early days, obviously we didn't have
that. I think the thing that we've leaned on really heavily was the value proposition to some of our partners building
on Zapier. It wasn't just, but most of time these platforms plays one of the big mechanics you see people building on
platforms is for distribution. I might go want to be in the Salesforce App Exchange because that way some more
Salesforce customers can learn about the fact that I exist and might discover me. For us we didn't have that, we didn't
have a big user base in the beginning. The value we gave to partners was around retention. If they built, they
integrated with Zapier, they got access to 50/60 of the time integrations that were maintained in scale and we're adding
more to it and they got all that for free.

Kevin Hale \[00:07:49\] - Oh.

Mike Knoop \[00:07:50\] - So it allows them to go say to their customers who are asking for these integrations, no
longer do they have to say, "Hey sorry, no, we'll put that on our do list or our feature backlog." And we all know how
that goes. They could start saying, "Hey, yes. You can do that with our product, go check out Zapier, here's a link."

Kevin Hale \[00:08:03\] - It was a way for them to say yes to customer requests. There's actually a way for you to do
this, go all the way here.

Mike Knoop \[00:08:08\] - There's value then beyond, you know just user acquisition that incentivized in the early days
to build on Zapier.

Kevin Hale \[00:08:15\] - Did it end up being that a lot of people on the front lines recommending you were then support
people? Because for us, in our company, customer thought was where all these feature requests would come in and so did
end up being. I mean I would imagine a lot of them were, hey here's the stock guy, here's how I satisfy you.

Mike Knoop \[00:08:33\] - Those are common, when you get listed a lot help documentation. Sales is also another avenue
where we get mentioned a lot, where we can, Zapier basically helps them close a deal with the customer that they're
trying to upsell or convert to a paid plan.

Kevin Hale \[00:08:46\] - Was that the start of your dominance in SEO stuff, is oh we get people sort of linking to us.

Mike Knoop \[00:08:54\] - That was a little, that was actually earlier. So we built our app directory before we built
the product. Before we launched at Tech Crunch, the whole story was that we've been working on Zapier for about five
months I think at that point. That the very first thing we did when we sat down, was we built our app directory which
was 90 pages, then we use that to try and gauge what people wanted us to build. We were building these manually, we
didn't, we had a very big opportunity cost in our time.

Kevin Hale \[00:09:20\] - So in the beginning how many apps that you guys integrate and do, before you actually had
people integrating and doing the work?

Mike Knoop \[00:09:29\] - It was 50 or 60.

Kevin Hale \[00:09:30\] - Yeah I think a 50 or 60.

Mike Knoop \[00:09:31\] - But we had 90 pages for I think a few hundred at that point and we had email collection on the
pages and classically in startup of just trying to understand, engage the market demand for this thing before you go
invest time to build it.

Craig Cannon \[00:09:41\] - But on launch you had 50?

Mike Knoop \[00:09:42\] - I think so, yeah.

Craig Cannon \[00:09:44\] - Because that was a startup weekend project initially.

Mike Knoop \[00:09:47\] - Yeah, that's where I met Wade at. Actually I known Bryan for about a year before we started
Zapier, but yeah, I met Wade the first time. I was actually going to pitch a different idea that startup weekend. I mean
not even worth talking about at this point. As soon as I heard Bryan pitch the idea for what was called API mixer at the
time, my eyes lit up and I was that's what I'm working on this weekend. So during the weekend we prototyped out actually
what Zapier is, to the core mechanics of mapping data between apps all came out of that weekend. I think we built PayPal
and Highrise and Twitter, were the first three apps.

Kevin Hale \[00:10:21\] - How did you pick those?

Mike Knoop \[00:10:24\] - It was more, we sat down and said what would be a cool use case that we could demonstrate this
prototype with. So during the final demo or during startup weekend, the mechanics of the weekend is you work for a
weekend and then you present to the rest of the crew on Sunday night. During the demo we said, hey wouldn't it be fun if
we get up on stage and have people actually tweet something live and then have people pay us something on PayPal and
then you could actually see Zap, the prototype of Zapier run and pull that data into a Highrise. The idea was we could
aggregate you know if someone pays you on PayPal and they're tweeting at you, you'd like to know that in your CRM so
that you could pay special attention when you're contacting them. So it kind of came out of a single use case and we
worked backwards from that.

Craig Cannon \[00:11:05\] - And so at what point do you end up doing YC?

Mike Knoop \[00:11:08\] - We applied actually twice. We got the email rejection the first time, we applied basically
with the prototype from startup weekend. So we had no customers, no traction and basically just three dudes from
Missouri. So totally useful exercise I think but it definitely lit a fire under us.

Kevin Hale \[00:11:25\] - What was useful about filling out the card.

Mike Knoop \[00:11:27\] - I wanted to show these people wrong.

Kevin Hale \[00:11:29\] - Did something change while filling out the application?

Mike Knoop \[00:11:33\] - It was helpful to think through what we didn't have yet, I think for that first time. It made
us realize some of the things around traction. There was a big delta and still optimistic with a prototype. But once we
got the email rejection, at that point we had enough hints of success so we're we're going to keep working on this and
it gave us actually more motivation to keep burning 40 hours of nights and weekends a week for the next few months. Then
the second time we applied, you know by that point we had had hundreds of conversations and chat logs and messages from
actually a lot of folks in the YC network, were even using the product. It was invite only at that point. We were having
folks pay, we had our first 10 people pass a hundred bucks to validate it and we turn down the price I think five bucks.
And we had a few hundred people who'd paid us an amount of money. There's a lot more social proof and validation that
hey this is a problem that a lot of people care about and could be useful.

Craig Cannon \[00:12:31\] - And so at that point, had you guys committed to being a fully remote company when you went
through YC? Did you even have employees?

Mike Knoop \[00:12:38\] - No, just the three of us and we hadn't, Zapier had been, I mentioned we've been doing nights
and weekends for that four or five months in early 2012.

Kevin Hale \[00:12:47\] - You guys still had jobs?

Mike Knoop \[00:12:48\] - Yeah, Bryan and Wade had full time jobs. I was still a full time student, actually a grad
student. I get the one star of dropping out to start Zapier. After you our full time jobs were over you know five
o'clock, we would go either back to our own apartments and work separately or we had one of our bosses let us run it,
use one of his offices to co work out of in the evenings and we'd go put in work until midnight, 1:00a.m. every night.
So it's kind of two full time, two full time jobs for the first few months.

Craig Cannon \[00:13:21\] - So Demo Day happens and then where do we go? What do you do?

Mike Knoop \[00:13:25\] - So obviously YC, one of the things is moving out to California. So that was one of the big
values of YC for us was the forcing function to go kind of all in. Right, no longer is it a side project. This is
actually the full time. Now we could...

Kevin Hale \[00:13:38\] - Did you not fully believe in it by then? Or is it like, you thought this is an interesting
hobby?

Mike Knoop \[00:13:44\] - Thinking back to that time it was, you think about our ambitions, right? It was hey, we wanted
to get this to a point where we could inspire ourselves, be our own bosses, controlling our schedule and it hadn't got
to the point where we could supplant our full time income. So it was kind of out of necessity that we were running the
company, building it that way. But once we got to YC, you get a little bit of initial capital, we got an apartment in
Sunnyvale and that kind of allowed us to focus all full time on it. After Demo Day we, actually leading up to Demo Day,
I remember one of the problems, early problems we ran into that summer was all three of us would wake up in the morning
and we were all doing customer support. We had a shared Gmail inbox or, not even that, an email would get copied into
all three of our inboxes and in order to support we would have to sit next to each other, so we wouldn't answer the same
email and we would be spending you know until noon, each morning just answering support tickets and trying to help
people get set up with the product. That was chewing up a lot of development and forward progress time. So the very
first hire we looked at was someone that helps out with support. We'd no network in the Bay Area and we didn't, you know
we just moved out three months ago, we didn't know anyone else. Our networks were from kind of our college networks and
from past jobs. When we started looking at the folks we thought might be a good fit for that, the one person who came to
mind

Mike Knoop \[00:15:01\] - was one of Wade's college roommates and he lived in Chicago at the time. We knew we couldn't
convince him to move to the Bay Area. We didn't want to and we thought back to, hey we were kind of doing Zapier
remotely before startup weekend or before YC, we could give that a try. This coincided with the exact time after YC
where I was, my wife, girlfriend at the time was finishing law school back in Missouri. So I was flying back and forth
every two weeks back to Missouri and then back out to California to work with Bryan and Wade. So kind of this perfect
storm of situation where it was well we have some confidence that we can do this remotely because we had been doing it
before and the people we want to hire want to be remote and I had to be remote for part of the time, so let's just give
it a go. So it was a very much an experiment in the early days, just to think, hey this was working, let's see if it can
continue to work.

Craig Cannon \[00:15:52\] - Did you have any kind of plan or structure? Or were you just like, well let's just see what
happens and make it work?

Mike Knoop \[00:15:58\] - You know more an inspiration than plan I'd say, you look at folks like base camp. At the time
WuFoo, at the time we'd seen at least small organizations that had been successful at building fully distributed remote
workforces. So I think there was more inspiration than anything.

Kevin Hale \[00:16:15\] - A lot of times for a lot of people they feel like the company isn't real until there's an
office. There's a lot of egos there. I think that's the kind of thing that's amazing about remote teams that actually
get really big. Somehow, they don't have something that's tied to the thing, the thing I need to show off. They're
comfortable saying, I got no place to show you, I work from my home. Did you guys even struggle at all about that? How
are we going to be a real serious company without this?

Mike Knoop \[00:16:48\] - It didn't hurt any efforts in terms of scaling the organization and certainly even, it's funny
how much, how pervasive that idea is because even I remember probably last year or the year before we'd still have
people joining the organization, who'd comment like, my parents want to know if I'm working in a real company right now.
It's well yeah, we're a 50 million ARR, we're a real company. But yeah it's still one of the reasons why I like some of
the PR things that it's actually useful because we can send those to friends and family and say hey look this isn't just
a side side show, this is a real.

Kevin Hale \[00:17:24\] - How did you not get caught into that trap? It has to come from the founders obviously.

Mike Knoop \[00:17:31\] - How did we believe that it was not a side project?

Kevin Hale \[00:17:34\] - Why is it that you never felt you needed to have an office?

Craig Cannon \[00:17:37\] - Well just peer pressure around startup norms.

Kevin Hale \[00:17:40\] - Exactly, why did you not succumb to that? What I often see a lot of people do is that I'm
spending this money because I think this is what it looks like to normalize me. Because this is actually very radical,
especially at that time, it's very radical to be I'm not going to have an office.

Mike Knoop \[00:17:55\] - I mean when we were talking to investors and whatnot through YC, lots of raised eyebrows, we'd
get folks turning us away strictly because of that. Even some of the folks who did, we went forward with still would be
like, hey when are you going to you know mature as an organization and get an office and start hiring locally, right?
Now you see a very different opinion in VCs. So which is fun to see that mindset shift. But how do we resist? I mean in
those early couple of first years between you 2012, 2014 it was largely driven out of I guess kind of the scrappy nature
of the organization. It was out of necessity because we weren't profitable yet. We had only raised a small amount of
money to help give us a backstop, to be able to scale a little bit faster than we otherwise would have. The networks of
folks we wanted to hire were remote. It was probably around 8 or 9 people into the organization when it stopped being an
experiment. I do remember specifically having that conversation, with Bryan and Wade, around this is working. It was
probably I think right after our first company retreat where we went up to Washington and had seven of us, where it felt
like this isn't just an experiment and an easy way to get better recruiting, this is actually a better way to run the
company.

Kevin Hale \[00:19:13\] - For us definitely it started off with the costs, we can't afford an office. But later on as
things were working we were just like, if you have this frugal mentality, there's nothing about the office and wanting
to have a commute that made any extra sense. We also had relocated from California to Florida. So it wasn't like, oh
yeah our office in Florida was going to be the driving thing for anyone. So for us it really just was like, I think
profitability was the biggest thing for us, we were making money. If someone had some criticism against why are you
doing it this way? It's I'm making tons of money. So I don't really care what you have to say about this.

Craig Cannon \[00:19:52\] - Does Wufoo still have the best exit investment ratio?

Kevin Hale \[00:19:56\] - The ratio yes, in terms of how much percentage of the company that YC owned or any of my angel
investors choose the output. I think we're still in the top ten biggest exits for YC still.

Craig Cannon \[00:20:08\] - Still?

Kevin Hale \[00:20:09\] - Because of how much equity that was owned. Because we didn't raise any money.

Craig Cannon \[00:20:12\] - You raised what?

Kevin Hale \[00:20:13\] - We raised $118,000. YC was $18,000 then and then we raised money from two angels P.B. and P.G.
and it was $50,000 each, and that was it.

Mike Knoop \[00:20:26\] - I think logistics and practicality were reasons why we believed in remote so much. The other
reason I think is actually a little bit more tied to, Bryan and Wade and I, how we'd like to work. In the early days, I
think it goes back to those nights and weekends, part of the reason of wanting to start Zapier in the first place was we
kind of wanted to own our own schedule and set our own goals and not be beholden to a giant organization telling us what
to do. We wanted to be very autonomous. One of, that is a company value, our number one value is default action and that
permeates all the way from the very beginning. We wanted to build Zapier as a company that we would want to work at. If
I'm going to go work at a a big company, I would want that level of autonomy and no one telling me that I have to be in
the office at 8:30 in the morning every day and I control my own schedule and be able to just go identify good things to
work on and do them.

Craig Cannon \[00:21:22\] - So as someone now who's hiring these people, do you have to filter out people who think that
they want that autonomy? Who think that they might want to be working alone for people who actually do? Is there a good
way to do that? how do you get the sense and really going to.

Kevin Hale \[00:21:38\] - Is it a company full of libertarians who care about freedom? Or is it a company full of
introverts? I imagine it's not one or the other but it's one of these things.

Mike Knoop \[00:21:47\] - I do think we probably attract folks that enjoy working alone more, not exclusively. We do
have quite a few folks who are extroverts in the organization, who've been successful and found ways to make it work.
One of the things I tell everyone who's going through the interview process is your work can't be your family. At Zapier
or any other distributed remote company, it's very easy to lean on your work as that social connection.

Kevin Hale \[00:22:15\] - That's a very rare healthy mindset.

Mike Knoop \[00:22:17\] - And if you're going to make it work at Zapier, you have to find a social network that's
outside the company. You'll get a little bit of it because we do two company retreats. You'll see their faces and names
all day in Slack. But whether it's side projects or hobbies or close friends or religion or family or whatever it is,
you'll definitely want to have one of those networks that's outside the work environment.

Kevin Hale \[00:22:40\] - Related to this what are other major characters that you look forward that you know this
person is going to be appropriate for remote work?

Mike Knoop \[00:22:46\] - Past experiences with remote is pretty good, is a pretty good signal because they know what
they're getting into. With that said we've had quite a few folks who haven't had past remote experience and they've been
very successful. But there is a learning curve attached to it. I think the biggest, one of the biggest things I look for
in interviewing, that tells me whether someone's going to be effective or not is how much they going to pull that first
value of defaulting action. Do they have past experiences where they did not take a consensus driven approach and
instead said, hey this is the right thing to do and I believe that this is the right thing to do and went and caused
some kind of action in their previous company or organization because they thought it was the right.

Kevin Hale \[00:23:24\] - But that sounds like a quality that's not just for remote work, it sounds like you just want
that period, for any company.

Mike Knoop \[00:23:29\] - That is one of the probably most surprising things I have discovered or observed, scaling
a 200 person real company to date is that the types of things you have to do in order to be a successful remote company,
make you just a generally better company, they are not unique to remote. However, you do have to figure them out earlier
and I think that is where a lot of the interesting things when people ask like, how do you run a remote company? I think
that's really where it is because we've had to invest really early on and how do we, what's our decision making
frameworks? How do we communicate as an organization? What are our processes? You have to get really explicit about your
processes in order to be successful, in order for folks to have the information that they need to be able to default
action and be able to know how to operate in this organization.

Craig Cannon \[00:24:16\] - So you mentioned this, I heard of this in another podcast about overlapping time zones and
making sure you don't unblock or block and unblock people. Nita Mehta, who I know, hey Nina, asked a question on Twitter
related to this and that is what's the best way to share work knowledge across designers working on different parts of
the product without distracting from focus and working time?

Mike Knoop \[00:24:38\] - There's a interesting underlying, I guess assumption here or observational I could say about
this which is, one of the benefits of remote work, a part one of the number one benefits is of course from recruiting.
You get to hire the best people anywhere in the world. A secondary benefit that I think isn't as obvious is that when
you're actually doing your job the best work gets done not when you're sitting next to someone and collaborating all
day, there's you have to get into deep work even for a role like product design which is very collaborative by nature.
You still have to have chunks of time like four hours at a time to go really deep and explore a lot of iterations, a lot
of different ideas. I think this is where it the process part of the organization gets so explicit is alright, in a
co-located company in an office you don't probably have a lot of explicit direction or process laid out as far as when
you're spending deep time versus when you're collaborating and coordinating with your co-workers because I can just tap
on the shoulder, Kevin and ask you what you think of the work I just did. Where it is in a remote team, where you just
have to be so much more explicit about what are the processes, individual people, individual teams follow when they want
to communicate.

Kevin Hale \[00:25:50\] - What were some mistakes you guys made in early days? You said you had to figured this out
earlier. Did you guys make any mistakes?

Mike Knoop \[00:25:59\] - I think one of the things that we figured out in the early days was when to be intentional
about how to be, how to keep, sounds generic. How to communicate. When to raise the bandwidth on communication. When
you're in a co-located organization, a company where I'm working in person with you. The default communication mode is
I'm going to get your attention and then I'm going to have a conversation with you and I have full, I have the full
range of bandwidth. I can use body language. I can stand up. I can use tone. It's full bandwidth between us. But I've
got 100% distracted you. I have your full attention. Now so it's like we're taking two people's time's up for this. In a
remote organization the default is 100% the opposite of the spectrum which is people don't communicate at all. If
they're using a Slack channel and that's your main office which is how we operate today. If two folks are on a team
together the default is kind of like you don't say anything. It's just a blinking text cursor, right? We have to be, we
have to figure out when are the right moments and how do we teach the organization when to move up that bandwidth chain.
To move from not talking at all because deep work is important to text is acceptable, it's Slack or email or something
like that to when to move that to video call. So when should I raise the bandwidth from typing this thing out, to
jumping on a video call. And then finally it's in person?

Kevin Hale \[00:27:25\] - Did you guys write these rules down?

Mike Knoop \[00:27:28\] - There's some transition moments to look out for I'd say. Those are the things that are written
down and share with company. So a good example of one that a lot of folks will be familiar with is Slack, many people
are typing, message then pops up. So if you like one of the things tell a lot of our teammates if you see that, that's
probably a really good signal that you should be like jumping on a video call at that point instead of wasting or not
wasting but instead of spending 10 man hours in Slack debating about this for an hour for 10 people, just get on a Zoom
call and hash it out for 10, 15 minutes and then summarize the decision back into the team chat tool you're using.
That's what I mean by identifying the moments that it's important to increase the bandwidth up.

Kevin Hale \[00:28:11\] - We had a rule when we were doing remote working where we knew that this was really painful.
What we hated was long discussions happening for too long and breaking this sort of deep work or maker schedule. So for
us, we changed the rule to be if you're discussing something for 15 minutes, at that 15 minute mark you got to stop and
go on to whatever the next thing you have to do, to get to what you say is default action. When we say it is all
discussions that have been paused, we set a time for this. We set it at the end of the week on Friday, when the team
meets together. It ended up being 90% at a time, that once they slept on it, they didn't even have to have a discussion.
They just magically figured something out or had a compromise, or realized something wasn't a big deal. So usually by
the time we get to Friday, not many things were ever brought up.

Craig Cannon \[00:29:02\] - Only the most important things surfaced.

Kevin Hale \[00:29:04\] - Exactly. I like this idea that what you are trying to default to is respecting someone else's
time and that the only time you start respecting is when you need to make it really efficient.

Craig Cannon \[00:29:18\] - But then what about on the other hand, where you are say you are stuck on a certain design
problem, programming problem, whatever it might be, at what point do you day like, okay, I'm going to break both of you
focuses and take your attention full on to solve this problem or try to solve it.

Mike Knoop \[00:29:31\] - That is a good question. The reality is even if I wanted to get your full attention, there's
no guarantee you are going to be able to get it in remote company. I may not have a path where I can go over and tap you
on your shoulder. I might be able to, you know DM you in Slack. I might be able to send you a calender invite and hope
to get 10 minutes on your calender this afternoon. But a lot of times, you don't have the same guarantee of being able
to some of the attention that you do in a co-location. That's actually good because it protects the attention of the
person who would otherwise get distracted. The thing some of the social, I guess norms of the organization of how we
address that is, one is in Slack. If you tag somebody in a message, @ tag them specifically, it's kind of the social
norm to acknowledge that within 24 hours. So we have some expectations like that. The reason we said 24 hours is because
we folks all across the world, the sun never sets on Zapier, I like to say. We have some of these social expectations
where there is going to be some, asynchronicity in how the organization works and operates. It's one of the reasons why
I think hiring for default action is so important is if you get blocked in whatever your primary task is and you're
waiting on someone else in the org, you have to have the bone to go figure out what are other smart things that I can
work on that are getting to contribute value

Mike Knoop \[00:30:52\] - to the goals and how do I better serve our customers here. If you're the type of person who as
soon as I get blocked, I'm just going to sit here until I'm told what to do next, you're not going to be successful at
Zapier or I'd argue most remote companies.

Kevin Hale \[00:31:05\] - How big is Zapier right now? How many employees?

Mike Knoop \[00:31:09\] - 200, we just crossed 200.

Kevin Hale \[00:31:10\] - Then your primary responsibility is all the design work that's done at Zapier.

Mike Knoop \[00:31:16\] - I spent a lot of time with our, helping our product teams figure out what to work on next. I
love spending time with our design and engineering teams.

Kevin Hale \[00:31:24\] - How big is the product and design team at Zapier?

Mike Knoop \[00:31:27\] - We've got about seven or eight product managers, a similar number of product designers and
then an engineering org that's about 50 folks, attached to that.

Kevin Hale \[00:31:38\] - So from my experience I know how much collaboration is necessary, especially at the start of
building out new products and sort of thinking through them and then also designing them. Then also part of the design
culture is critiques. So to me that was one of the things that was really difficult. Luckily at Wufoo it was I was the
only designer, we never grew to be on 10 people so.

Mike Knoop \[00:32:00\] - It's easy to communicate with yourself.

Kevin Hale \[00:32:02\] - Exactly. I'm really curious what's done differently for your design team and product team to
make that sort of work?

Mike Knoop \[00:32:11\] - One of the most important relationships in the organization is the relationship within product
managers and product designers. I don't think I'm saying anything new or novel here by saying that, but it's certainly
true for us which is when we are thinking about staffing and hiring a team we're making sure that those two folks are
intentionally building rapport, they're spending a lot of time together and they have a very strong shared ownership
over the goals that they're working towards.

Kevin Hale \[00:32:35\] - How do you do that remote work wise? That's the thing that's difficult especially when you're
trying to respect everyone's bandwidth.

Mike Knoop \[00:32:41\] - Yeah, in the earlier days when we had started the scaling which we'd started kind of scaling
these teams maybe about a year or two ago. I'll admit it was more ad hoc, we were figuring out this process still. These
days with 200, we've been a lot more explicit with processes. We started using OKRs as an alignment mechanism and a
designer and a PM and an engineer all own share.

Kevin Hale \[00:33:08\] - A lot of the companies can have weird definitions of OKR. It's how do you guys define OKRs?

Mike Knoop \[00:33:13\] - An objective that that team is trying to accomplish. We want to you know increase how many
users are able to set up at Zap by 10% this quarter or something like that. And that's something that a PM, an
engineering manager and a product designer would have shared ownership over. It gives a lot of focus to that team and it
also kind of helps elevate everyone's role to be thinking about the impact on the customer first. I think what the thing
I've noticed that happens in scaling Zapier is, there's a tendency for engineering and PM design to kind of specialize
in their own areas. They have their own unique things they are thinking about all the time, right? Engineer might be
thinking all day about the user experience. Engineering is thinking all day about estimates and delivering, refactoring
and code quality. The PM is thinking about business impact. If you don't give them some kind of, if there isn't some
kind of shared system for how they should value the things that are prioritizing, you get a lot of us versus them
mentality that kind of creeps into the organization. Where it's well, why won't the designer do this? Why won't the
engineer do this?

Kevin Hale \[00:34:12\] - So you give teams OKRs versus individuals?

Mike Knoop \[00:34:15\] - Yes.

Kevin Hale \[00:34:15\] - Gotcha.

Mike Knoop \[00:34:16\] - It's something new we're starting to do but so far it's been pretty fruitful in building that
alignment across teams.

Craig Cannon \[00:34:22\] - So how is the team checking in on each other? Is it a stand up type thing everyday?

Mike Knoop \[00:34:27\] - Every team does a little different actually. One of the things about Zapier that is cool to
see is a lot of teams experiment with some of the process.

Kevin Hale \[00:34:34\] - You give a lot of autonomy to different teams to try a bunch of stuff?

Mike Knoop \[00:34:37\] - Yes we do, and OKRs are kind of our framework for how we pull up, how we make that not
chaotic. If that makes sense. I like to think about, the things that are important to be consistent across teams are the
interfaces. You need to make sure that the interface between teams is consistent so that both teams know how...

Kevin Hale \[00:34:55\] - Can you be specific, what does that mean?

Mike Knoop \[00:34:57\] - How am I dependent on you? Or what is the API layer if it's two product teams that are
building in the same area of the product? Or if it's design, what's the ownership between and where's that handoff
what's the scope of ownership between two teams? Another layer might be, we use Jira for doing a lot of our issue
tracking and project management, there is some level of consistency that is important to have across all of our product
teams using our product management software so that we can build some observability into the product development process
across the company. So we can get a sense of where are we doing well, where are we not doing well. Identifying issues
where we might be over investing in feature work or under investing in feature work or tech debt and things like that.
So there's some level of consistency that's important but we do generally try to give a lot of individual autonomy to
these EPD trios too.

Kevin Hale \[00:35:50\] - How are the teams created?

Mike Knoop \[00:35:53\] - Mostly on an...

Kevin Hale \[00:35:54\] - Do you guys assign them? Or the people kind of have a draft or?

Mike Knoop \[00:35:58\] - They are picked and we hire into them, I guess. So we will create a lane at the leadership
level of the organization. Hey, here is a new opportunity we want to go after. Here's an area of the product that we
aren't addressing or part of the conversion funnel that won't improve. We'll then staff into that. So we've got a decent
recruiting team now.

Kevin Hale \[00:36:19\] - So whatever team that someone's on they kind of stay with that team all the way through the
life of Zapier?

Mike Knoop \[00:36:24\] - Mostly, they're long running teams. I'll say that. We've had folks switch, I wouldn't say
we've actually. Our earliest product team is only a 1 1/2, 2 years old. So and some of those folks have shifted. We've
had staff provokes restaff from one team to another where there was another part of the product they wanted to work on
and they had some expertise that could be used somewhere else. Maybe we brought in this person's a really senior level,
experienced at engineering and we've just brought in more staff level or associate level engineer. We want to get them
to work together.

Kevin Hale \[00:36:53\] - What's the timeframe for these OKRs? Are they quarterly goals, yearly goals, you probably have
a range of them.

Mike Knoop \[00:37:01\] - Annual and monthly tends to be the two kind of extremes. Annual just to know alright where are
we? What are we working towards over the course of year? What is this product team trying to accomplish over the course
of 2019? Then kind of monthly check ins against that where they break those down.

Craig Cannon \[00:37:16\] - Can you break down how an average team might handle tracking for a newcomer? How does that
workflow actually go down?

Mike Knoop \[00:37:22\] - This is still new to the organization. So I feel like I need to give the caveat we're learning
a lot still with this. We've been practicing with OKRs at the exec level for the last two quarters in 2018 which gave us
enough confidence that hey this is actually a very effective tool for us to help align and allow everyone, all these
different teams and people in the organization to be autonomous and default to action in ways that they want. That we
wanted to start rolling it out to all the individual teams this year for 2019. Practically speaking I think the best
version of this and this is aspirational, I don't think we're quite there yet is you've got some high level direction
being set by leadership of the organization. What are we trying to accomplish, right? And Zapier case, we're trying to
build a piece of productivity software that anyone can use. How do we get Zapier adopted by tens of millions of people
some day. You've got this high level direction and strategy being set. Then at the team level and lower in the
organization there's a lot of work that is happening that needs to figure out okay, where is that aligned and how does
that bubble up? There's kind of a meet in the middle approach where you kind of want the work that's happening, 50% of
it to be kind of top down driven and I think 50% of it being bottom up. Because in reality, the exec team leadership is
never going to have perfect insight into all the pieces of work that happen across the organization. I don't think
that's what something OKRs is particularly useful for is to define

Mike Knoop \[00:38:53\] - every piece of work you're doing. I think it's largely useful for helping you prioritize and
make hard trade offs and have discussions. This is one of the things that's great about writing down our process
documentation in Zapier, writing down our decision making processes because when it's written down you have something to
debate about. I can go to you and say hey can we debate whether this is the right thing we should be spending our time
on? It so much easier to do that when there's an artifact that you're talking about as opposed to a group of people with
different ideas in their head about what is important to have it. It just removes this layer of conflict in the
organization.

Kevin Hale \[00:39:28\] - It also, discussions can drift when it's not tied to the artifact. What other tools do you
guys use? I don't have any doubt that you guys still use Zapier itself to help you guys.

Mike Knoop \[00:39:39\] - We are happy Zapiers, yes.

Kevin Hale \[00:39:43\] - But I remember in the early days talking to you guys, you guys built a lot of tools for
yourself and I'm just wondering right now what's the most helpful tools that you guys are using? Either that you've
built yourself or that other that you're using from other companies.

Mike Knoop \[00:39:55\] - The one that, I actually built this one in the early days. It's a tool called Async, is what
the name of it internally. It's an internal blog essentially. We use Slack as kind of our company office for better for
worse. This is where folks usually log in to in the morning. This is where work gets talked about. We've got about one
of the trouble with that, especially as we scaled, and anyone, any remote company or any team that uses Slack will be
able to tell you this. It gets the overwhelming amount of noise in Slack. How do you keep up with Slack? And we're very
early on we set the expectation that Slack is not a tool you're expected to keep up with in Zapier. You are free to
leave channels. In fact we encourage it.

Kevin Hale \[00:40:33\] - That is fascinating.

Mike Knoop \[00:40:34\] - There's a feature in Slack where you can turn off the leave join notifications and we turn
that off because we wanted to give folks the social comfort to be able to leave channels without feeling awkward.

Kevin Hale \[00:40:45\] - Because it feels like pressure. It's like I'm behind on my homework.

Mike Knoop \[00:40:48\] - There's some social pressure.

Craig Cannon \[00:40:49\] - I just end up muting those channels rather than leaving them.

Mike Knoop \[00:40:51\] - Yes, we actually have a course we're working on for how to effectively use Slack at Zapier. In
the early days, we set that expectation of that's how we use that tool. One of the things that kind of was missing that
I saw was what is our more thoughtful to use maybe the Daniel Kahneman idea, slow thinking version of Slack. Slack is
where work gets talked about, right? It's quick responses. In the moment, I need a decision, okay. Where does our final
work get talked about or where does our more deeper work that we're thinking more long term and putting together where
are final reports getting shown to the organization? How does that get shown to, how do the right people get notified
that I have something I need to read and make a decision and think about. So this is where in the early days, I actually
got inspired by Nick Francis over at Help Scout. They were using a tool, another remote team, called P2, it was a
plugins for Wordpress. That it was basically, it's kind of like a Twitter feed. Automatic was using this internally and
that's how they run their.

Kevin Hale \[00:41:53\] - Really old.

Mike Knoop \[00:41:54\] - It is. We used it at Zapier for a good six months and it was pretty good. It started breaking
and we wanted to customize it. This was one of the most interesting things of why I like investing in tools is you can
tweak and change them to match the level of company you are at essentially. As your company gets bigger, you are going
to run into these new bottlenecks and you can start layering in and customizing the tool instead of having to go throw
the tool away and pull a new one and then relearn it. In the early days P2 started breaking for us, it didn't scale. It
didn't timed or off system was funny enough the reason why I wanted to rebuild it. So I built a version of internally
called Async which can just internal blog. This was kind of the tool that one of the cadences that we have in Zapier is
every week we ask everyone to write a Friday update for what they worked on. This is kind of the heartbeat of the
organization.

Craig Cannon \[00:42:44\] - So that goes up on the blog?

Mike Knoop \[00:42:46\] - It goes up on Async, yes. This work grew up in the early days you got 20 people, 30 people.
You get to read everybody's Friday updates. You get to know every thing, every decision that made, everything people are
learning, all the work that's happening. When you get to 70 or 80.

Craig Cannon \[00:42:58\] - 100 blog posts, yeah.

Mike Knoop \[00:43:00\] - That starts taking a full day just to read all the information. So you start to run into the
same problems as Slack does. Information overload. But because we own the tool, we can tweak it and tailor to how we
like, we want to run the organization and how we make decisions and how we want communication to work. We started
building a default feed view where it was a curation layer in terms of, okay, who are your immediate direct reports. Who
are the folks you need to follow. You can follow folks, you can create custom feed views to build the curation. We work
with managers to onboarding employees to set up their views in the right way so that it's curated so that they get that
just the information they need.

Craig Cannon \[00:43:39\] - So does email have a specific role? Or is it kind of a catch all for you?

Mike Knoop \[00:43:42\] - We don't send any internal email.

Kevin Hale \[00:43:45\] - Really that's like my fantasy.

Craig Cannon \[00:43:47\] - Full stop.

Mike Knoop \[00:43:48\] - None. So we use email, email is used in a few ways in Zapier. Of course, we do email support.
So we use Help Scout and all of our emails. Basically if there's any internal to external communication, so when we're
talking with our partners or with customers, obviously that happens over email but internally there is no email.

Kevin Hale \[00:44:07\] - It's just Slack and Async.

Mike Knoop \[00:44:08\] - Those are our tools. We also use Quip for a long form documentation.

Kevin Hale \[00:44:14\] - What's Quip?

Mike Knoop \[00:44:16\] - It's a Wiki, it's a collaborate of Wiki. Kind of Google Docs mixed with Wiki.

Kevin Hale \[00:44:21\] - And that's more for documentation.

Mike Knoop \[00:44:23\] - Yes. Document processes, hiring rubrics, things that kind of need to live a little bit longer
in the organization. Both Async and Slack are feed views that roll off.

Kevin Hale \[00:44:32\] - One thing people were surprised about with us that with it was how much time we spent
development wise on internal tools actually. It was almost 30 to 40% of development time was us building stuff for
ourselves. It's why we were able to grow and only be at a 10 person company...

Craig Cannon \[00:44:49\] - Yeah, efficiency.

Kevin Hale \[00:44:49\] - for so long. So what is that ratio for you guys? And do you have special internal tools teams
you know that Facebook is kind of famous for?

Mike Knoop \[00:44:58\] - We did last year, we had invested in an internal team which was helping scaling some of the
Async software that we're talking about. I for better or worse have been kind of the internal tools manager for the last
six months. I was building this OKRs. We actually built our own OKR software into Async. One of the beautiful parts of
it is when you're updating your OKR, it's got annotations that tie into the posts you're writing. So we've got this nice
long running graph of hey here's this metric I'm moving over the year you can see oh here's where we launched this
feature, here's where we made this decision and you can see it annotated on the graph.

Kevin Hale \[00:45:33\] - But right now it's kind of just organic teams make their own stuff.

Mike Knoop \[00:45:36\] - It does tend to be a little more organic. I'll say in the early days I think we invested more
time in internal tools and it's something I'd love to spend more time on actually.

Kevin Hale \[00:45:46\] - I was just thinking, just listening to Async, and I know remember this for us. A lot of our
internal tools, ended up being YC companies down the line in the future. So it's am I hearing Async, can we just oh God
that's a startup right there.

Mike Knoop \[00:45:58\] - More recently most of the internal things that get built in Zapier today are apps on Zapier.
We have a lot of folks in our engineering team and even more broadly on our support team and product team that will
build features into Zapier by building an app on Zapier. This is kind of where some of the innovation of Zapier comes
from. Quite a few of the most popular apps on Zapier were built by one engineer and a side project at a retreat
hackathon. Just for fun because it was, hey we're going to add this little bit of functionality to the product that
doesn't exist. Maybe it's the ability...

Kevin Hale \[00:46:29\] - But it actually made it out on to the product?

Mike Knoop \[00:46:30\] - Yeah, eventually.

Kevin Hale \[00:46:31\] - That's actually the biggest criticism for lots of corporate hackathons. People spend all week
and get really excited and they never make it to the light of day.

Mike Knoop \[00:46:38\] - We tried pretty hard to make pick our hackathon projects and we curated them in a way that we
thought that there was some value that could eventually make it out to customers in some format or would help customers
in some way.

Craig Cannon \[00:46:50\] - So what are the other things you guys do to kind of keep employee and founder morale high
across a remote team?

Mike Knoop \[00:46:57\] - Probably the biggest thing we do is we do two company retreats a year. Even the fact, even
though we're 100% remote there is still a lot of value for getting in person. We don't discount that. You get to build a
lot empathy. You get to build relationships with folks and it allows you to kind of be, assume best intent the rest of
the year. When you're in Slack and you're in that, working on that tense project and someone leaves you know writes a
message that might be a little more curt than it should have been. It's oh, I can hear their voice in my head I know who
that is, I understand who that is. I'm not going to jump off and assume that they were trying to be mean to me or
something like that. That helps smooth over a lot of issues that I think can happen when you are primarily using text
based communication tools, where you do lose a lot of that tone. You have to try really hard to use tone and it's just
that's one of the first things that can easily get lost when you're in tense moments. So there is a lot of value for
building in-person relationships still. So we do two company retreats a year, where we fly the whole company into
usually some cool resort or hotel or place around the U.S.

Kevin Hale \[00:48:05\] - How long are those retreats?

Mike Knoop \[00:48:06\] - It's a week, Monday to Friday.

Kevin Hale \[00:48:09\] - What do you guys do during that time? Is it just hanging out or I imagine it's some structure?

Mike Knoop \[00:48:13\] - We've tried a few formats. I mentioned the hackathon. We've traditionally done a hackathon
most of the week and then we would have a couple days set up for teams to kind of break out in their own individual
silos. This past retreat we tried something different though. We tried giving, one of the things we do a lot, we run a
lot of company surveys and we try to evolve and iterate how we run the company.

Kevin Hale \[00:48:37\] - It doesn't mean you do a lot, how often?

Mike Knoop \[00:48:39\] - I mean anytime we're doing a company wide thing, there's probably going to be a survey sent
out about to give feedback so we can improve for next time. It is tied into Slack. There is an email though too, I will
admit that.

Craig Cannon \[00:48:57\] - So you are not there yet.

Mike Knoop \[00:48:59\] - I still do keep my Gmail tab open but there is a slack time. But we, every a company retreat,
there's a survey. We send out two companies surveys a year. I ran a product or a company survey last year so we do a lot
of that.

Kevin Hale \[00:49:13\] - What's the best thing you guys do at the retreat that you didn't do it on the first one? What
has changed that you are this is way better to do it this way?

Mike Knoop \[00:49:19\] - So this last time the thing we experimented with was we added unstructured time. We had always
planned every hour of every retreat to date.

Kevin Hale \[00:49:32\] - It's interesting you didn't think about it earlier.

Mike Knoop \[00:49:34\] - I know, right? It's probably a bias that's being thinking, we're in a remote mind set, right?
Which is design the process, how do we want people collaborating. How do we want them connecting. Make that happen and I
think some of our managers feel responsible to make sure their teams are taken care of and people know what they're
doing and what they should be spending time on. So there was just the sense where from the top, from management
perspective, we were over planning all the hours and one of the things that prevents is cross team coordination or cross
team conversation. What if one person from the data team and one person from support and one an engineer had this cool
topic that they talked about at maybe one of our unconference sessions. They wanted to go hack on an idea. There was no
time for that to happen in the past format and because it was completely top down planned. So we added these two
afternoon sessions of unstructured time where we set the expectation that hey it's still a work day but figure out how
to best utilize this time with your team and your peers.

Kevin Hale \[00:50:31\] - How do you know it worked well?

Mike Knoop \[00:50:36\] - Mostly through feedback at this point. I was anxious about it going in it was so, we added
this process in because of feedback we'd gotten before. People specifically asked for time to do this. So we added it
in. I was still anxious that folks would not take advantage of it. I was worried that they would just default to what
they would do if they weren't at the retreat, right? Just do what, I'm going to go do normal work and work on my roadmap
or work on support tickets in isolation. But we want to take advantage of the fact we're here. So I overemphasized in
almost all my conversations, the time leading up to the retreat to take advantage of the time. When I walked around and
just observed the different groups of people that were caught coordinating in those afternoon sessions, I was surprised
at how many people took advantage of the time, given my anxiety I guess that it was not.

Kevin Hale \[00:51:27\] - I think it shouldn't be surprising when you're hiring a bunch people who are default action,
self driven etc. Then you bring them all together I think they'll do the right thing.

Mike Knoop \[00:51:35\] - It worked out well and I will continue to do something like that in future retreats I think.

Kevin Hale \[00:51:41\] - Can we talk about, I'm curious, how do you guys do design critiques? How does that work in
this collaborate environment. It's so difficult to even do it in person. So how do you, and you guys have an interface
that has to bridge hundreds and hundreds of apps together and hundreds and hundreds of different types of features
together. It's so complex and I'm trying to think of doing that without people really close and diving deep on the
problem. How does that work for you guys?

Mike Knoop \[00:52:11\] - I guess I'd be interested to ask why, what assumptions do you have that makes. What previous
belief or experience do you have Kevin that says I have to be sitting next to you in order to solve a problem like that?

Kevin Hale \[00:52:26\] - I think it's one of those things where for design in particular it's hard to point, circle,
re-sketch etc. There's some things that on pen and paper, in person I can show. Now I know that there's ways to do it
where it's oh I can do this show it by video but it seems slower and more inefficient. I'm just wondering is there
things that you could do to compensate?

Mike Knoop \[00:52:48\] - I see.

Kevin Hale \[00:52:49\] - How do you think about it differently?

Mike Knoop \[00:52:53\] - It comes back down to being explicit again. So one of the exercises that I've done quite a few
times with the team has been the nine box design exercises.

Kevin Hale \[00:53:03\] - What's that?

Mike Knoop \[00:53:05\] - Fold your paper into nine boxes and you have two minutes to sketch nine different ideas of a
solution and then you have everyone present their nine ideas and then you do a remix usually for a longer five minute
session and you come out with a lot of just divergent ideas in a short amount of time. That time compression on being
able to come up with an individual idea is intentional to force folks not to get too deep in the thinking and just to go
wide instead of deep. I've run these over Zoom calls where I'll literally ask. I did this with the entire company last
year where, a little while ago, where I asked, it was maybe, at that point maybe 70 or 80 people, everyone bring paper,
bring sharpie and I gave the problem statement upfront and everyone's just on a Zoom call with their video on and
sitting on the table right and drawing on the paper and then hold it up and they talk about it. I had them take a
picture and post it in the Slack channel. So it was a higher fidelity version that they could see and they're holding up
and pointing to it.

Kevin Hale \[00:53:57\] - I actually see how that's stronger than normal design collaboration. When everyone's in a room
there's a pressure of no I can't, I don't want to look bad or if I'm trying to sketch and figure something out, it feels
uncomfortable to do so in front of a bunch of other people. So I can see how having everyone separate is like, oh,
you're working your own, kind of say it feels a little bit more safer to be daring.

Mike Knoop \[00:54:19\] - There were instances where I remember still having to encourage folks, hey show it even if you
think it's bad because that's some of the things you think are weird ideas often end up leading to the right idea even
if they're initially weird, will just trigger a different way of thinking about a problem that hasn't been thought of
before. So another process we have in addition to doing kind of team exercises like this. One of our more go to
processes that we've, has been working really well for us the last year was we were doing a Tuesday, Thursday,
essentially design review across several product teams. So we would invite several product managers, several product
designers and the Tuesday/Thursday a cadence was how we built in that feedback we process. Where it's okay, I want to
show something to team and get feedback on it, get critique and then it's instead of only doing one a week, we'd have to
wait a whole other cycle. There's a forcing function to turnaround and iterate and go deep on it.

Kevin Hale \[00:55:18\] - In 48 hours.

Mike Knoop \[00:55:19\] - It's 48 hours to then turnaround and show it back on Thursday and show it again. So it's kind
of a bit of a mix where you still get that deep work in between the two review check ins but it's still on a Zoom call.
Well one of the things that I like to ask people to do on Zoom calls, especially in design collaboration sessions is
don't mute yourself. Zapier's built up this interesting norms around what is Zoom etiquette, right? When to unmute
yourself. When do jump on video, all that kind of stuff. So we kind of, I have to intentionally ask folks to break that
habit and say okay, for this please don't keep me on mute. So to encourage folks to jump in. I want folks to feel
comfortable, not waiting to give their feedback but just to generate a little bit more randomness in that conversation.
I think this is probably one of the things that is very interesting about remote and there's a question someone ask
around how do you be innovative as a remote company? There is some amount of randomness that you, I think is probably
desirable in an organization. Certainly you don't want it to be 50 or 100% random, you want some low level of randomness
in terms of people talking to each other or what's being shared.

Craig Cannon \[00:56:35\] - I think they're kind of alluding to serendipitous chance encounters, right? Weird water
cooler conversation.

Mike Knoop \[00:56:42\] - One of the things we do is process, it's called the pair buddies. There's actually three
people in this, now we've got big enough where we've a bot that randomly just picks people that are in a Slack channel
and says hey, you two people should, there three folks now, here's 30 minutes to chat. The idea is no agenda. Just a 30
minute call where you share whatever you are working on and talk to some of those ideas.

Kevin Hale \[00:57:03\] - I actually think this idea is interesting. I actually think a lot of companies or
organizations that group over optimize for serendipity. They're what about that chance? But to me serendipity, some
random thing happen all of us and we have a great idea, that's like hitting the lotto. To me, optimizing for the lotto
is very weird. 99% of the companies, we have a whole list of stuff that we have to get done. So to me it's optimizing
for that should always be the first priority not for the off chance of these other chance encounters.

Mike Knoop \[00:57:33\] - I'm always wondering like, what is the right ratio? Because I think back to our hackathons,
right? Where this is a totally individual driven thing. We had great things that got built that no one would have top
down planned to go build and surprised us in terms of how popular it became.

Kevin Hale \[00:57:48\] - But I think it works out better when you build up a kind of pressure and then it needs a
release. Where all of a sudden it's oh, this is my opportunity for this. Versus, well not forcing it. Just oh let's have
it all together and then maybe something will sort of bubble up.

Craig Cannon \[00:58:04\] - To me a lot of it ends up getting solved by just knowing what other people are working on
which is a problem across every company I've ever worked at before. So I've no idea what Kevin's done in the past two
weeks but I know Kevin's been on the podcast with me. I know Kevin's been crushing an email. But what have you actually
been doing?

Mike Knoop \[00:58:22\] - We don't have that problem, we have the other problem which is I have too much, too many
opportunities to learn what other people are working on. How do I curate it down to alright, who are the people I need
to know about? What's working, so that and do my job effectively?

Craig Cannon \[00:58:34\] - So kind of wrapping up, I'm curious about if I were to be starting out a remote company,
what's the framework you would offer to say, okay, you should do X, Y and Z things and set yourself up for success to
really get the most out of this?

Mike Knoop \[00:58:47\] - I think it is one of the reasons why it is so hard to add remote on to an existing company is
because remote, when you see folks talk about it and ask questions about, it's always very process and tools based. I
think the honest answer is that it's more of a cultural change than it is a process and tools thing. So folks that are
starting out actually I think are at an advantage in this fact because there is no culture yet. It is you or it is your
co-founders or whatever. You have the chance to set up the culture in a way that encourages things that are going to
work in a remote organization. So again thinking through things like defaulting action and encouraging empowering
autonomy and how are we going to make decisions and thinking through some of those things in the early days. Being
explicit about writing down and sharing all the work that you do and building it a habit into the organization to write
down everything that's done and share that with colleagues, as opposed to relying on content sharing over like a Zoom
call, that's a ephemeral and can get lost. Those are the cultural habits and norms that are a lot harder to change in
the future because you need everybody doing it. I think there's a structural advantage for folks that are a 100%
distributed. That everyone's in an equal boat, they're all in the same boat, right? I'm all in my home office. If other
people aren't doing that thing then I'm not going to be successful or happy in my own job. So you can take advantage of
that in the early days.

Mike Knoop \[01:00:21\] - It's a lot easier to set that initial culture up where it's okay, we do want folks to be
individually empowered to make decisions. We want to hire folks that have demonstrated this ability in the past. We want
folks that are good at written communication, that over communicate even. One of the things I often tell new engineers
that are joining Zapier in practice centers is, I have to encourage over communication a lot. Again coming back to the
default, no one talks. It is more important and it feels awkward at first to be just sharing a status update with an
empty Slack channel or a Slack channel where you're not expecting a reply. That's a habit to build. You have to realize
how useful that is to the person on the other end where hey I might get blocked on something and that status update you
gave four hours ago helps give me some context on something that I should be doing or how to solve a problem in a
certain way that otherwise would get blocked on, you know request response cycle from them and especially across time
zones it's tough. So yeah, just setting up the right values around autonomy and written communication are probably the
two most important.

Kevin Hale \[01:01:26\] - You guys wrote a book about this, right?

Mike Knoop \[01:01:28\] - We did. It's a ebook on running a remote company. It's a couple years out of date from a
process standpoint but it gets the cultural status right.

Kevin Hale \[01:01:37\] - What's the biggest thing you wish you could update in the book?

Mike Knoop \[01:01:44\] - So one, I mean the biggest thing, probably how we've scaled Async, would be what I would go
back and to add to it. The book was written at a time where we didn't, we had enough people that could somewhat
reasonably consume all the context that was published there on a monthly basis or on a daily basis or weekly basis,
that's not true anymore. We've had to be a lot more thoughtful and intentional about what are the, is it a push vs. pull
kind of mechanism? What's the kind of algorithm that powers the default feed view, that shows content that everybody
should be reading in the organization on a weekly basis?

Kevin Hale \[01:02:23\] - Then what are thought leaders and other people in this space that you guys follow for
inspiration that other people should definitely check out?

Mike Knoop \[01:02:31\] - There's several folks that are bigger than us that have run remote organizations. It's kind of
a little bit of rare air, once you get beyond 50 people though or even 20 people fully remote. Folks like GitLab is
bigger than us. Envision is another organization that's largely remote. Automatic is another early one that we looked up
to. I think the biggest thing again we took away from those was not from a process standpoint or even a cultural value
standpoint it was, hey it exists, this is not impossible, right? Someone has proved that it is possible. We are not
having to trail blaze the fact that it is possible to have a company with that many people that's fully remote. Now they
have it slightly and all those organizations have slightly different value mechanisms than we do. So that's what we're
going to figure out as we scale, is alright, how do we apply that size of the organization to where we're at? That's the
biggest takeaway, I would say is that remote is possible, there's very large organizations that are doing it. So you're
in good company if you decide to build a fully remote company.

Craig Cannon \[01:03:38\] - That's a great place to wrap it up. Alright, thank you.

Mike Knoop \[01:03:40\] - Thanks Craig.

