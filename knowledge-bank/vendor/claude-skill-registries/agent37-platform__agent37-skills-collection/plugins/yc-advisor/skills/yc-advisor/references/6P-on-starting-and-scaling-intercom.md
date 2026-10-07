# On Starting and Scaling Intercom

**Author:** Des Traynor
**Type:** Video
**URL:** https://www.ycombinator.com/library/6P-on-starting-and-scaling-intercom

---

On Starting and Scaling Intercom

# On Starting and Scaling Intercom

by Des Traynor

Be Wary of Solving a Small, Rare Problem - Des Traynor of Intercom - YouTube

[Photo image of Y Combinator](https://www.youtube.com/channel/UCcefcZRL2oaA_uBNeo5UOWg?embeds_referring_euri=https%3A%2F%2Fwww.ycombinator.com%2F&embeds_referring_origin=https%3A%2F%2Fwww.ycombinator.com)

Y Combinator

2.1M subscribers

[Be Wary of Solving a Small, Rare Problem - Des Traynor of Intercom](https://www.youtube.com/watch?v=P6pQyB6ACrk)

Y Combinator

Search

Info

Shopping

Tap to unmute

If playback doesn't begin shortly, try restarting your device.

You're signed out

Videos you watch may be added to the TV's watch history and influence TV recommendations. To avoid this, cancel and sign in to YouTube on your computer.

CancelConfirm

Up NextCancelAutoplay is paused

[Y Combinator](https://www.youtube.com/channel/UCcefcZRL2oaA_uBNeo5UOWg)

Subscribe

Subscribed

All the world is changing around technology and you may contribute a line of code. What will yours be?

Subscribe for startup advice, founder stories, and a look inside Y Combinator.

What is Y Combinator?
We invest $500,000 in every startup and work intensively with the founders for three months. For the life of their company, founders have access to the most powerful community in the world, essential advice, later-stage funding and programs, recruiting resources, and exclusive deals.

Visit ycombinator.com to learn more.

[The Truth About The AI Bubble\\
\\
30:23](https://www.youtube.com/watch?v=cqrJzG03ENE)

[There's an Art to Getting Brilliant People to Surprise Themselves - Kevin Slavin of The Shed\\
\\
1:02:10](https://www.youtube.com/watch?v=xamF4CBk69Y)

Share

Include playlist

An error occurred while retrieving sharing information. Please try again later.

Watch later

Share

Copy link

From Y Combinator

[ycombinator.com\\
\\
**Y Combinator** \\
\\
Apply for startup funding.](http://ycombinator.com/?ref=youtube)

Watch on

0:00

0:00 / 1:09:37

•Watch full videoLive

•
Intro

41K views

Over 1 year ago

[Des Traynor](https://twitter.com/destraynor) is the cofounder of [Intercom](https://www.intercom.com/).

Here's his talk [Product Strategy Means Saying No](https://www.youtube.com/watch?v=9AM6QQlgLSQ) and the [blog](https://blog.intercom.com/product-strategy-means-saying-no/)

[Product Strategy is About Saying No \| Des Traynor - YouTube](https://blog.intercom.com/product-strategy-means-saying-no/)

[Photo image of Business of Software](https://www.youtube.com/channel/UCHD9iLa5C-d9QnVmY9v7toA?embeds_referring_euri=https%3A%2F%2Fwww.ycombinator.com%2F)

Business of Software

1.05K subscribers

[Product Strategy is About Saying No \| Des Traynor](https://www.youtube.com/watch?v=9AM6QQlgLSQ)

Business of Software

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

[post](https://blog.intercom.com/product-strategy-means-saying-no/).

# Transcript

Craig Cannon \[00:00:00\] - Hey, what's up, this is Craig
Cannon and you're listening to Y Combinator's podcast. Today's episode is with Des Traynor. Des is the co-founder of
Intercom, and he's also given a bunch of talks about product. Many of you guys requested him as a guest, so Des came on
to talk about product, he also talked a bunch about how he's changed roles since he co-founded Intercom, and he shared a
bunch of lessons that he's picked up along the way. Alright, here we go. How did you meet your co-founder and decide to
get going?

Des Traynor \[00:00:29\] - I was originally a computer
science student and I started a Ph.D. and my Ph.D. was an attempt to see if we could automatically measure how good a
programmer is, basically, so put them through a variety of simulated code and ask them to say what the output would be,
and we had some really interesting findings from that research, but I got bored. I got bored for two reasons, one is
that some of the findings were slightly uncomfortable for some universities, because I was basically saying that,"Hey,
this person you're saying is getting a 65% score, I actually don't think they can program because they can't tell me
what this code outputs," and people don't want to hear that, obviously.

Craig Cannon \[00:01:03\] - Just because they figured out
how to take exams well?

Des Traynor \[00:01:05\] - Yes, precisely, typically the
way, and this is true worldwide, the way people in universities would mark a piece of code is they say, alright, we'll
give them three points if they have a for loop and two points if they have an if statement and people just learnt that
off. The phenomena is like the template based marking encourages template based learning so people like know what a
solution should look like but they have no idea what it does right? It looks like they're learning off Latin or
something. That finding became more and more uncomfortable for universities and as I said, "Hey I would like to study
some of your students, here is my hypothesis." They were like, "No thanks." I started writing a blog instead because
that was the alternative to publishing and write about this stuff. I started writing my design and usability and one day
somebody commented on my blog, his name was Eoghan McCabe and he was organizing this coffee morning in Dublin city for
all the people who worked on the internet which is a small group and this is like 2006. I went along and actually it's a
funny story. I met Eoghan for the first time there who I started to hang out with. I also met my wife for the first time
in that same evening.

Craig Cannon \[00:02:11\] - Really? Wow, high value.

Des Traynor \[00:02:12\] - Yeah, it was, exactly. A good
day's work. I actually went and took a different job with a consultant agency and then for one year me and Eoghan kind
of kept in touch and then one day he emailed me and said hey I'm starting my own thing, you do want to get involved? We
started working. We had an agency called Contrast. It was a design agency, and then we were following the 37Signals
model, and we wanted to have a side project that we would eventually pivot to. Our side project was a tool called
Exceptional, it was a Ruby on Rails based error handler and would alert developers and notify them, "Hey this piece went
wrong and here is who was affected." That was the normal trajectory and then one day we were getting really frustrating
trying to communicate with our users because we have thousands and thousands of people using our product but the product
would frequently perform slowly or fall over and the state of the internet back in 2010 wasn't good. The infrastructure
wasn't there, there was no Stripe. If we wanted to mail all of our paying customers to apologize for some downtime it
was like, log into the PayPal dashboard, get an export of all your subscriptions, run that through some Perl to extract
the email addresses, import the email addresses into CampaignMonitor or MailChimp, then send in a notification, get all
the replies and all the auto replies and shit back into your email, resurrect your email after like two hours of going
through it trying to fix it up and all of that we had to do every single time

Des Traynor \[00:03:34\] - we wanted to say something to
our customers. That was the norm. One day we had this little message pop up in the bottom right hand corner of our
product saying, "Hey sorry we were down yesterday, but here are the changes today. Read our blog post." People were
like, "Oh," and we saw a lot of engagement in the blog post, must better than we ever saw with email. Then we started to
riff from there, like what if people could reply to us? Imagine talking to somebody while they're using your product and
letting them talk back. We started adding these little bits and pieces and features and every new iteration was like
what if we could see everyone who has read the message and everyone who hasn't? That became the basis of what we call an
active user list. Who is using your product right now? All of this in 2017 is taken for granted but this did not exist
in 2011. What if we could send a message to some people but not all people? What if we could send it at a specific time?
Today we call that like behavioral marketing automation but back then we were just like this makes sense. I remember
distinctly reading one comment going like, "I'm not actually much of a fan of your product but this little chat thing is
amazing. Or like, maybe you should all go build that or something like that." Obviously we had been thinking that a lot
but the feedback we were getting from people really just pushed us and pushed us so eventually we sold Exceptional. It
went on to become a part of Rackspace. Then we had this little thing for talking to users but

Des Traynor \[00:04:50\] - we had a new problem, we had
no users. We had to go and build the back end if you like so that we could give it to other people so that we would have
our own customers so that we would know.

Craig Cannon \[00:04:57\] - I was wondering if you were
just going to steal all the users from Exceptional and move over. This was maybe the most asked question for you.

Des Traynor \[00:05:04\] - Yes, the folks that acquired
Exceptional, they were actually kind enough to use Intercom to push one last message out to say, "Hey, we are the new
owners, we're here, we're great, we're going to love you for the rest of your life et cetera. If you're curious what
happened to the old guy, they're off working on this thing called Intercom, go check it out." It was like July 1, 2011
we got to the top of Hacker News for Intercom, a cool new product or whatever. The engagement in that thread I still
read it now and then, that was the first one where I was like I knew that other people had this problem.

Craig Cannon \[00:05:38\] - And was that the HN, was that
your first push for signups?

Des Traynor \[00:05:42\] - Yeah, pretty much, we had a
reasonable sort of contact list from people who had used our previous product, people who we knew from conferences or
people who had read our old blog, so we had an audience of sorts. And my job in the early days was literally mailing
people every day and be like "Here's what Intercom could look like inside your product, do you want to give it a try?"
One by one, literally one by one we were onboarding people. If they said yes they'd jump on a Skype call or our CTO
Ciaran, he'd walk them through the installation. This is what it took back then and then one by one we were winning
customers. And then once we felt we had a relatively smooth signup flow, we're like well let's tell the world and see
what happens.

Craig Cannon \[00:06:17\] - Okay, 'cause you guys have
made a giant content push, was that going on previously with the other company?

Des Traynor \[00:06:22\] - Yeah, and when we were a
consultancy, content was the way we would try to get attention so we could attract the clients and then later on grow a
user base for Exceptional. But with Intercom it was very, we knew we were good at it, I specifically it was my job. So I
was like right well, the Intercom today we're a lot more polished in terms of saying what we're actually selling, but
back then it was just like we need cool startup folks to read this and then if we can win their trust then we'll be
like, "Hey, try and sell them this. And that was a very common question, what was the basis of your content strategy?
And I'm like write shit startup people read and then try and tell them about your product every now and then. And that
was what we did, I think I wrote 93 of the first 100 posts, and it was all like here's how you grow a user base, here's
how you should think about funding, here's how you should name your product, it was anything we felt like we had any bit
of expertise in, we'd write a post and every now and then we'd be like, "Hh, here's something else we added to
Intercom."

Craig Cannon \[00:07:22\] - Yeah, because that's a
critical understanding that we could blow right past. So many people in their content just try new sales pitches over
and over and it never works and they can't figure out why.

Des Traynor \[00:07:32\] - You're totally correct. A lot
of people's attempt at content marketing is I want Intercom's user base, so they blog so I just need to write about my
product all the time, whereas we actually took very much like it's content first, marketing second. The content has to
be good. The advice I'd give people usually is like think about who your actual target user is and think about all the
problems in their life that you can help them with. And then try and help them as much as you can and then every now and
then hopefully if you're ideally aligned your product also solves one of their problems. For Intercom it's usually like,
you want to grow your web app or you want to grow you user base, we can do that. But we know to get your attention we
have to plant many seeds, so we'll talk about design, we'll talk about product, we'll talk about product strategy, we'll
talk about tech news, whatever makes sense to us we'll talk about as long as the criteria we have is generally it should
be like timeless content, it should always be roughly true. And that's how we have a very big readership of our blog
today, and it is our dominant traffic source. But that wasn't true for the first 100 posts.

Craig Cannon \[00:08:42\] - Well I was wondering, were
you punching above your weight at that time? Did it feel weird writing these kind of authoritative posts?

Des Traynor \[00:08:49\] - it definitely didn't feel
weird. The reason I would say I felt confident to do it is because I was never trying to say like, "Here's how you scale
a 100 million dollar ARR company or whatever," and I hate when people try to do that. We were always talking about, all
of our experiences were based on the two products we had, Intercom and Exceptional, and it was like the lessons that we
had learned. I was always careful to try and qualify like hey, look we're at 6,000 active users, we were at zero four
months ago, I can talk to you about the zero to 6,000 thing, I think that's relatively safe. And so the areas where
maybe it was slightly more, if we talked about branding or how to name your company or think about your product vision,
yeah there are definitely better people in the industry, but they're not fucking writing these posts. We're what you
get, do you want it?

Craig Cannon \[00:09:42\] - At that time did you consider
yourself a strategist?

Des Traynor \[00:09:46\] - No, I considered myself a
startup person, if you know what I mean.

Craig Cannon \[00:09:51\] - Because you were a CS
undergrad, right?

Des Traynor \[00:09:52\] - Yeah computer science, for
sure.

Craig Cannon \[00:09:54\] - Were you the CTO at the time?

Des Traynor \[00:09:57\] - No, I was just a computer
science undergrad in fact all of the founders did computer science but our COO and I moved into design as our career, I
was like a UX designer, usability testing, interaction design, that sort of stuff. Eoghan was primarily a visual
designer. And then our other two engineers... was like a person that built the front end of Intercom, did the little
messenger piece, and then our CTO basically owned the rest.

Craig Cannon \[00:10:19\] - Okay, gotcha. Because I was
curious about what your role has been throughout the process, how has it shifted and we talked before you were on
camera, like it's already shifting again.

Des Traynor \[00:10:30\] - It will always shift, I do
kind of go to wherever the biggest problem that I think I can help with is. That's kind of what usually attracts me. I
want Intercom to be a world class company and wherever I see areas where I think I can help level up I'll jump in. In
the very early days I worked sort of three jobs. Work with Eoghan on kind of company vision strategy, that sort of
stuff, I work with Ciaran and David on what they're actually building day to day, and then basically talk to users and
try to help people find out about Intercom. I was blogging, I used to webinars at like seven PM in the evening in Dublin
for people over here. I just do live like here, let me talk to you about anything to do with the product. It was,
anywhere I was needed. In the early days I was very much working on what we were building and then trying to tell people
about it. And then as we grew we brought in more senior product folk and then at some point, maybe around 25 people I
was like alright, product looks like it's in a good place. What's the next biggest thing? And it turns out we had no
customer support at this time. I was also doing a bit of data and we had maybe one or two people so I jumped on customer
support, I worked with Jeff who's our Director of upport still today and built that team and there's other teams that
came along since then, we had maybe like People Ops was the next thing, bits of recruiting were the next thing. And then
about two years ago it was marketing, so we kind of got to a point where we think Intercom's

Des Traynor \[00:11:52\] - definitely, the product
definitely going the right place, we look to kind of refine our ideas about how we bring it to market, how we describe
it, how we explain what it is, what's our relationship with the media, how we pay for advertising, all that sort of
stuff, so that's what I've been working on for two years and as he said, there will be future problems I'm sure.

Craig Cannon \[00:12:08\] - But it's so cool because so
rarely founders shift roles in entirely separate categories, right? It's very common when you start a company to start
doing everything and then focus, but to shift roles between groups is different. How do you learn those skills?

Des Traynor \[00:12:24\] - Yeah, that is a good question
and I do agree it's not the default thing usually, you find your corner and you stay in it for a very good reason, it's
what you're good at. Two years ago I was, when I was starting at marketing I felt a little intimidated because marketing
itself, it's not really, like there's no real Marketing 101 sort of thing, there's no marketing for dummies, there's no
Pickaxe book for marketing.

Craig Cannon \[00:12:49\] - Well it's less quantifiable
than this code runs or this code doesn't ruin.

Des Traynor \[00:12:54\] - Precisely and if I sit here
and name someone who's good at marketing and you're not let's say, Apple, everyone's opinion is kind of different.
Frankly marketers don't write many articles about how to think about things or how to structure things. I've talked to
maybe 50 different VPs of Marketing at this point about how a marketing order is structured. And they're all different,
like not just different as in ooh you put one person there, but substantively different, even in terms of sometimes
brand design is inside, sometimes it's outside, some of it's communications and reports to CEO, sometimes it reports to
a part of marketing, all of that's different. So I did find it quite intimidating early on and more so than the other
areas where I felt there's a lot of literature and there's a lot of best practices out there. Marketing was a challenge
and the way I actually kind of learned was I did get connected to great companies and basically sit and learn and absorb
and see what worked and what didn't. I wouldn't say I kicked ass at marketing at Intercom, rather I've made plenty of
mistakes there as well, and fundamentally based on misunderstanding what roles will work, what types of people will
work, what approaches will work, so I definitely know a lot more today and I feel like today I'd feel justified in
applying for a marketing job somewhere.

Craig Cannon \[00:14:04\] - Or writing a marketing blog
post?

Des Traynor \[00:14:05\] - Yeah for sure, but two years
ago I was aware of two things. I was aware that we'd tried hiring marketers and we hadn't worked out well, so I figured
that at the very least if I could learn enough to know what good looks like, that would be great.

Craig Cannon \[00:14:20\] - Were there a couple rules
that you kind of maybe learned just through experience over the past couple years that you could share?

Des Traynor \[00:14:26\] - Rules?

Craig Cannon \[00:14:27\] - Of marketing?

Des Traynor \[00:14:29\] - Yeah, I guess there's
definitely principles I've just picked up over time. One is the general narrative about marketing, people will tell, or
the engineer's approach to marketing is like, "We're going to hire a marketer and they're going to find the keywords
that are CAC LTV positive, that is the customer activity cost is less than the LTV and we're going to dump all of our 50
million dollars into that, and it's going to spit out 100 million dollars." And like basically that never happens, and
someone's going to be like, "Sorry Des, I have one case where," it never happens for all intents and purposes. And so I
think whenever you have someone promising you that it's usually absolute horseshit. The next I guess, let me just take a
look and see, so I've got, the next piece is understanding how people buy your product is more important then selling
your product, if you know what I mean. One big eye-opener for me was that like some people come shopping for Intercom.
Some people come shopping for a chat widget on a website. Some people come looking for a solution to their growth
challenges. And they're all actually looking for Intercom. There are various levels of abstraction, various ways people
can buy your product. And I think a lot of times companies get soaked into selling a product one particular way and
maybe they pick one of those things and, "We are live chat." It's like yes you're live chat, and some people know that
they need live chat as in they've gone to the doctor's, they've gotten the diagnosis, and they're like, we need live
chat.

Craig Cannon \[00:16:00\] - They talk to their friend and
their friend recommends it.

Des Traynor \[00:16:02\] - Yeah, and so you have this
brand one like your friend says install intercom. Then you have this maybe, you've changed marketing leaders and are
like hey we need live chat on our site, that worked in the old place. Okay, now you go shopping for live chat. So we
need to be in that shopping for live chat. Then we have people whoa re like hey, I've just joined a new company and one
of the challenges is actually we're not converting leads in our homepage. Now at this point should they install
Optimize, they should install Intercom, should they redesign their homepage, should they hire a better designer? We're
now in a much bigger fight but we still need to put our hand up and say hey, that's actually a business problem we can
affect too. One of the big lessons for us at Intercom is learning to be able to put our hand up in all of those
different shopping journeys. So that was one, whenever I speak to other people who are maybe earlier on in their
marketing career and they're looking for guidance, typically what they find is, enter Google Advertising. They're
bidding on their own company name, right? And I'm like, that's cool but that's not what people are shopping for, right?

Craig Cannon \[00:16:57\] - Well it's challenge that we
have at YC. For people in the tech industry who know they want to do an accelerator, the likelihood that they know YC is
pretty high, and we can convince them to do YC possibly. But then there are other people who have no idea what a startup
is or have this vague notion is and we have to speak to them as well. And so what strategies do you guys use to appeal
to that type of person or each of those people without alienating the others?

Des Traynor \[00:17:25\] - And so this is kind of a core
of how we think about it. When you have somebody who say is, obviously YC has a brand. Some people just shop for YC and
maybe you're so dominant you don't even need to bid on that because they're going to find you anyway. But also in some
sense there is no substitute, right? As you take a step back, some people just want the money. And so I'll take YC, I'll
take Techstars, I'll take 500 Startups, whatever. And now you're into an actual ground war. Now the question is should
you bid on 500 Startups, the keyword, right? Should you try and say we are better and here's why we are better than
them, if you're shopping for both come check this out, right? That's like the sort of competitive angle to marketing,
and if you can pull that off you now get to compete for all, the super set of the traffic, not just the YC shoppers
anymore, right? And then you have the people who have a startup and they don't know if they want money or not. In which
case, now these people aren't Googling. They aren't going, hypothetically if I was to start a startup, what would I
want?

Craig Cannon \[00:18:28\] - We could own that long
search term.

Des Traynor \[00:18:30\] - Yeah, you'd be the only
person bidding on it and that would be you testing it. Basically what happens is the amount, the size is getting bigger
each time. There are more people thinking about starting a startup than there are people looking for YC today, right? At
the same time, your likelihood of conversion is going down, someone looking for YC is going to convert, somebody who's
thinking about taking incubator money, they might not convert. Your pitch needs to be more all-inclusive at this, sort
of far-sighted. You can't start, if I'm saying, "Hey I'm thinking about taking some incubator money," you can't start
with, "12 weeks you're going to have dinners with founders, we had Joel Spolsky in last," I need to be like, "Whoa, talk
to me about the concept of incubation first of all," get me buying that thing first and then I'll learn why you're best.
So for intercom, what that looks like is we need to convince you that you should care about your customers, right? If
you care about your customers and you care about the value of a customer relationship, we can get people on board with
that, they're more like okay, we've built one bridge. The next bridge we'd like to talk to you about is why messaging is
a great way to build a relationship. So none of these pitches individually convert, this is where people are like why
the fuck do you write this shit, Des? You write a whole piece that's effusive about why messaging is the future and
messaging your customers is important,

Des Traynor \[00:19:50\] - and like okay, so I guess the
relationships are important. I get that messaging builds relationship and we're like okay, cool. Now do you get, now
they talked about Intercom's messaging, and our philosophy to messenger. And you see you have this cascading series of
thought leadership sort of ideas that bring you from, in our world, I would like to grow a big user base all the way
through to I need Intercom yesterday, and in your world that might be like, I'm curious about incubator cash. And you
want to catch them at that point and maybe the blog post you write there like how to think about early financing, or
maybe it's like why you should move to the valley, or whatever it is. And you want to catch them at that point and then
you can walk them down the logical path where like there's obviously no other choice, why on earth wouldn't you go YC.
And that's the actual approach that we've played out at Intercom, retrospectively I can tell you that has been my
content marketing strategy, but we didn't start with, the thinking wasn't that crisp at the start.

Craig Cannon \[00:20:47\] - No, and are you tracking
someone throughout this journey?

Des Traynor \[00:20:48\] - Kind of, we're not doing a
great job on that to be honest. We will get there and we've just made some good new hires in marketing who will kind of
improve that sort of side of things, but we do know that yes, we can see the amount of repeat readers we have and we can
see the most popular articles and we can see the articles that convert most, no like this is exactly where the, maybe
slightly more Fischer-Price approach to marketing would be like, "Hey Des I've noticed that the piece about Intercom's
new messenger converts a lot, why don't you write a lot more of those posts?" It doesn't actually work that way. You
have to do the warm-ups to get them to there. That's the piece that people don't necessarily get. In general, the
marketing world is one where you move from like this is really hard to attribute and it costs a lot of money down to hey
we spent seven cents and it kicked ass. But that whole thing is a spectrum and you have to be willing to do the
unattributable things to kind of grow awareness or whatever. And then on the far side, yes the attributable stuff which
looks really really successful works, but if you only do that, everything suffers. One example, I have a friend who
basically he ran paid marketing for a very very big sort of sports gambling firm, and he kicked ass one year, he ran all
his campaigns phenomenally well, and the CEO looks at sort of the brand spend and looks at the online digital
attributable spend and CEO says, "I'm going to give you all the budget

Des Traynor \[00:22:18\] - 'cause you're the one who's
performant. Next year, what happens? So he's got all the budget, poor brand person's got nothing, so you go absolutely
batshit heavy on spending everything you can, but all your conversion rates are dropping, you're like, what's going on
here? And it turns out that your conversion rates are dropping because you don't have the same brand penetration that
you did, and this is why you need to think about this thing holistically, you need to ask yourself are we building the
brand? Are we creating the right brand resonance and relevance that we can cash in on, 'cause the cashing in on, I don't
want to say it's easy, it's an absolute expertise, but it sits on a platform of work that has to be done before it. The
only exception is when you've got a fast moving consumer good, like if you're selling shower heads on Facebook, just
target people who say the word shower, hit them hard, we don't need to create this whole big sort of movement around
showering, people already shower. But yeah, most of us, specifically in our industry we're not selling fast moving
consumer goods. And we're not selling necessarily obvious things either. It's not a given that you have to install a
podcast plugin, or...

Craig Cannon \[00:23:20\] - That was the thing that I
was literally dealing with this morning before we met up. There's an issue with one of the audio files in one of the
podcasts I'm editing, and I don't know the word for what's going wrong with it, I know there must be some effect that I
can apply to fix it, but I don't even know what the fucking word is. And I'm sure that's the case with Intercom, I'm
sure that's the case with YC, and so we have to figure out what the synonyms are.

Des Traynor \[00:23:43\] - People don't know they need
it yet, and yes precisely, and the other marketing principle I'll tell you, you can't sell somebody on the solution
until they've bought the problem, right? Me trying to pitch you on the audio wargler or whatever the hell it is you
need, until you have that problem you're not even, you don't give a shit, right? Finding those moments is a really
important challenge as well, and then as you said the synonyms just casting a wide net. There's like 10 ways to describe
a problem, for Intercom it could be retention is suffering or it could be like we need to accelerate user growth or it's
like how do we maintain user growth, or it's like how do I influence customer engagement? They're all actually looking
for the same thing which might be like, I want to speak to my users but at specific times, they get them to take the
right actions so they can move forward. They're all shopping for the exact same thing but they have a million different
ways to describe it, and we need to be there and put our hand up for every single one of those. And not just like, point
them to this is the other mistake people make, pointing them like alright, so I've got the bid term, I'm going to point
them at the home page. That doesn't work 'cause if someone says I want to onboard my users better because onboarding
conversion rates are poor, and we're like yeah we can bid on all that, we know we're good at all that, but if we point
you to [Intercom.com](http://intercom.com/), we're going to say we're an all in one marketing
platform where our mission is to make internet business,

Des Traynor \[00:24:54\] - wait, back back back, sorry.
Hang on, I thought I was onto something there. We actually need to be like you want to onboard, you're in the right
place. And at that point Intercom isn't actually the big deal, it's just like let's keep the message about onboarding
here. Let me hold your hand and walk you through how we're going to help you with the onboarding problem and then we'll
be like okay. And then after a while we'll be like oh by the way, this whole thing? Intercom. That's how that works.

Craig Cannon \[00:25:15\] - A lot of people wanted you
to talk about product. How do you think about all this content marketing effort in the context of your product shifting
and evolving over time, how do you merge those two things if Intercom is known for one thing and you have this whole
history and all this SEO around that, when your products start shifting how do you think about it?

Des Traynor \[00:25:37\] - I've often said that product
and marketing and code and design are all like renderings of the same core idea. To give you an example, one core idea
at Intercom is like sending the right message to the right person at the right time and at the right place. And we have
Ruby code that does that. And we have a designed screen called the campaign editor that does that, and I have a blog
post that does this and I have a whole conference talk that I do this in as well. They're all carrying the same message
in different ideas. At the core of every one of our products, educate, respond, and engage, we have these core ideas,
and we have loads of different ways to talk about them, case studies on how to help, why it matters, what the big vision
for them each is, and as we've evolved our product we've had to bring more ideas into the fold. At the very core at
Intercom, we're about making internet business personal. We can never bring something in that's the opposite of that,
right? But we can certainly have a collection of ideas that we can represent. When we launched new product in December
last year called Educate, it was basically our take on a knowledge base for proactively offering and educational content
to your customers. And what that means was, I have to sit down with marketing and be like alright, well we need to work
out what are the core ideas here. And right events, what can we do in terms of events? Content, what are we going to do?

Des Traynor \[00:27:02\] - Books, are we going to do
books? How are we going to get this into a podcast? What are the landing pages for this? What are all the ways people
bid on this? Media, how are we going to talk to the press about this? And you're kind of looking for like every one,
here's the core idea, you're all welcome to take your own lens or your own flavor of it, but we all need to push on this
idea. Bad things happen I think either when your product, sorry your product and your marketing are out of sync. Karen
Peacock, who's our COO, she always says build what you sell, sell what you build. If you're not doing both of those
things, you're in fucking trouble, basically. But similarly, I think that's the first challenge. If we're selling
onboarding and you think you're building auto mailing, we're in trouble, alright? And then similarly I think the piece
that a lot of startups and we've had to fight to get this right is making sure that your brand is also resonant with the
same ideas. So you can't, I often think of, you know Michelin, the people who do Michelin star restaurants? You know
it's a tire company?

Craig Cannon \[00:28:01\] - I do.

Des Traynor \[00:28:01\] - So I often, that's like
orthogonal brands in a lot of ways, no one finishes their meal and goes mmm, I'm going to buy some tires. I do worry, I
see a lot of startups, specifically folks who try to copy say something like Stripes brand and are like we want to be
cool with developers too. And that's great, but you're selling an online writing app. Developers aren't your thing, but
they have this really cool tech blog but that's literally, it's not against what you're doing but it's totally, it just
also happens to happen at the same time, it's not helping you at all, right?

Craig Cannon \[00:28:35\] - Well how do you think about
product in that way then? Because obviously you guys are a big company, you could release a ton of products. How do you
figure out what's going to resonate with your customers and your brand?

Des Traynor \[00:28:46\] - At the very very start we set
our stall out to say our mission is to make internet business personal. At the very core, anytime we have to make a
decision about whether or not we do a product, we ask ourselves does this make business more personal on the internet?
You can sort of say, would we release a tool that made it easy to spam people you've never talked to before? Well no,
because that's totally opposite. Would we release a tool that lets you stream soccer live to your mobile phone? No.

Craig Cannon \[00:29:15\] - I did read that in an
interview though, that's what you would be working on.

Des Traynor \[00:29:19\] - Yeah, but that's sort of our
core sort of guardrail for the product that just basically, does it do that? And then within there, the we have other
sort of, let's say rubrics for what's the next most important way we could tackle the impersonality of digital business?
And so we kind of move through it like that, Every change we make in product has to trigger changes in product
marketing, product design, brand, content marketing, sales et cetera.

Craig Cannon \[00:29:54\] - Yeah.

Des Traynor \[00:29:55\] - You do have to have this sort
of like inside out sort of thing where at the very core we decide, all right, we're now also going to do push
notifications. Well why are they personal? Okay, well let's expand from there. Has to weep out into everything,
otherwise your product, your marketing, and your brand get out of sync and that's when bad things happen. I'm really,
truly--

Craig Cannon \[00:30:15\] - Well you've talked about
this in the context of hiring and growth. Because you become out of sync and then it kind of expounds, or rather grows
exponentially, if you start hiring the wrong people.

Des Traynor \[00:30:25\] - Yes, totally. It's so easy
to... The point I make exactly in sort of hiring is if you hire one person who's not on the same page and you let them
hire people, they're going to hire more people who are not on the same page and next thing you have whole wings of the
company working against you in bad ways. And they don't think they're being malicious, they think they're helping, but
sometimes they can be doing the exact wrong thing but more often they're just doing something that's literally not
helping. It's not hurting, but they may as well not be doing it.

Craig Cannon \[00:30:55\] - Right, it's just not
working. How do you guard against that?

Des Traynor \[00:31:01\] - Alignment is like, I think
like... We had a big event here two nights ago, Inside Intercom, it's like our blog on tour, we had like a thousand
people, and one of the talks... gave was all about keeping people aligned. Basically the things that when companies go
through these really fast growth periods, there's a few things that always, always get left behind. One of them is new
hire onboarding. Person number five joining a four-person company, has full access to everyone and basically absolute
immersion therapy, they learn everything by osmosis. Person number 66 joining a 65-person company gets access to three
people, each of whom have been have been there less than a year. It's not the same thing, but almost always no one's
designed it any differently. They're just like, oh well, so the logical conclusion is that the company goes off course.
So we invested head-on, like we made versions of this mistake quite a lot in the early days. Today, we obsess over
new-hire onboarding. When I leave here I'll be heading back to Dublin, Tuesday morning that's all I'm doing is just
meeting people. Letting them know what are we doing, what are we actually doing here, why are doing it, why do we care,
what are the problems faced, why does it matter to us, how do we do it, like how do we actually work, how does work
happen at Intercom.

Craig Cannon \[00:32:19\] - In practical terms, this
means a one-on-one meeting with you just talking.

Des Traynor \[00:32:23\] - Yeah, it'll be a combination
of sort of... Firstly it's a bunch of new-hires, it'll be a presentation from me about walking through absolutely
everything, and then it will be one-on-one meetings and then we'll take it from there. Because they're not all reporting
to me in this case, so they'll be with they're manager to keep that going. But I would say that I still believe that
we're probably not even doing enough, but I think most companies don't do enough. They don't really think about what's
the experience of being person number 397 at your company? And then they act somehow shocked, like I can't believe they
thought it was okay to ship that. Well show me the guardrails that stopped her, how on earth were they supposed to work
that out?

Craig Cannon \[00:33:03\] - Yeah, absolutely. Yeah, you
can't really blame them. We do it, we need to do a better job here as well. Andy Cook asked a question related to this,
"In addition to hiring, what has been the biggest challenge with scaling the organization?"

Des Traynor \[00:33:18\] - Yeah, I guess there's a few
ones that are probably more typical, but eventually you end up hiring into areas that you don't understand at all. And
your best bet at that point is to go and find somebody who you think is doing a good job at it. But it's still a version
of the same flawed logic, which is, I think I can work this out--

Craig Cannon \[00:33:42\] - Right, they wrote a blog
post about this.

Des Traynor \[00:33:45\] - They probably know it all.
There's some version of that and it's very easy when you're dipping your toes in areas that you really don't understand
to basically be bullshitted. Specifically in marketing and sales land this is more common. Marketers and sales people
are good at marketing to you and selling to you so if you've never hired a sales person before, don't be shocked if the
first person that comes to you sells you on the role. It's obvious in hindsight sort of thing, but I think it's
genuinely tough to break outside of your own area of expertise and hire well there. You will learn it, but it's takes
longer and you don't get the same immersion that you did from say studying computer science or something like that.
That's definitely one. I think we probably more than other companies, we started with two offices, so in some sense we
never had to deal with the like, oh my god, now we're two offices. We were always two. But that's been a challenge,
working out the right headcounts in the right places. We now have four offices, we're in Dublin, London, San Francisco,
and Chicago, so we're spread. It makes some things really tricky, like today, we had a show and tell sort of thing where
everyone who works in any sort of aspect, any who kicked ass basically, closed a great sales deal, built a great piece
of product, or whatever, they all line up to present. Orchestrating that is so hard across all the time zones, across
all the offices, it's far from easy

Des Traynor \[00:35:09\] - and you have to do these sort
of little rituals to keep the whole company on the same page, but maintaining that is hard. And it was hard for us at
the very start. Today we can spend a lot of money of video conferencing and shit like that, but early on it was rough.

Craig Cannon \[00:35:24\] - Do you spend money flying
people around to hang out with each other?

Des Traynor \[00:35:28\] - Mm-hmm.

Craig Cannon \[00:35:28\] - Do you do like any kind of
everyone comes together conference?

Des Traynor \[00:35:31\] - We haven't done a sort of
all-company, all-hands, in I think like two and half, three years, but we definitely do like version of it. So any team
that's distributed will always come together once to four times a year depending on the type of team. Then the
leadership level, the executive level, we'll do like six times a year, something like that. So there's versions of it.
For me what that means is, if I get on flight number EI147 everyone knows me because... You don't want to be on
Foursquare like the mayor of the lounges in the airports and all that, but c'est la vie.

Craig Cannon \[00:36:02\] - What hasn't worked out?
What's been really hard for you personally?

Des Traynor \[00:36:08\] - Marketing has been tough. The
stuff I've really struggled with is hiring senior leaders in a function where you don't understand it well is tough.
It's a big challenge and they're never bad people. When you're going shopping for directors and senior directors and
VPs, you're only really talking to accomplished people. It's not like you get them in and it turns out they don't now
how to write code or something. It's very much the feedback period to whether or not they're strategy is correct for the
company can be six months to a year, which is long. The impact if they're going the wrong direction can be negative,
because you have to bet on them. Which means you have to empower them to hire, empower them to do everything that they
need to do, empower them to spend the budget, et cetera. And then you get to find out in quite awhile if all this pays
back. The piece that's hard, I actually don't think I've made that many mistakes, per se, but I've just paid quite an
emotional tax of just a great degree of fear and anxiety in the recruiting process. And then I guess, honestly,
post-hire you're like I need to do everything I can to make this a success. I think that's genuinely something I've
struggled with. Learning a lot people stuff has been hard. Learning how to ensure that we actually have a good policy
for say performance management. I think those conversations, and even on podcasts like this it's easier for me to not
talk about stuff, but of course companies have to fire people and do all sorts of stuff.

Craig Cannon \[00:37:39\] - Totally.

Des Traynor \[00:37:40\] - No one ever wants to hear it
of course, but I think getting to a place where you understand that these things should be openly discussed and
professional conversations by people who know what they're doing. Getting there, genuinely I think every startup I talk
to takes them way too long. And I think if I was to do it all again, of course, you'd be more for familiar, but I think
there's a lot of obvious pitfalls. And yet I don't think you can necessarily preempt every mistake. As in, even if I
told somebody who was just starting their first startup, here's everything I know about this, some of it's like, "Yeah
that's doesn't apply to me." They're not going to, you know, it's back to that point I was saying earlier, you're not
going to buy the solution until you've bought the problem. And I'm trying to force feed them--

Craig Cannon \[00:38:29\] - Were there any books or
anything? Because I feel similarly, so many people have given me advice and I've had to fall into the hole myself before
I could really learn it. But where there any books or podcasts that really helped you figure out how to manage people
better?

Des Traynor \[00:38:45\] - Rands has a book called
"Managing Humans" and I thought that was... It's written entirely in story form. So it's no preachy, it's very much like
here's stories from his time. Now I'm sure they're either fake or embellished, or modified to protect the innocent, but
it's written in a very sort of conversational tone. It kind of reminds of "The Hard Thing About Hard Things," by Ben
Harrowitz. Every story, they're almost like fortune cookies, when you think about it for a second, like shit, I have
been in that situation or I put somebody in that situation, or I was that guy. And I think it's a great book for that
reason. I think at the very least what I see it do for first time managers is it opens their eyes to the idea that
there's more going on to managing than just being really good at engineering. they realize there's an actual whole craft
here that they need to perfect to take the next steps in their career. And I think it's a great book for that, but it's
also a book I think the third you read it you start picking up better lessons than you did the first time.

Craig Cannon \[00:39:45\] - Okay, and so just to shift
gears back to product again, if someone is just getting started out, what do you advise them on thinking about products?
Just framing the entire company. Where do you have them start?

Des Traynor \[00:40:04\] - I guess, I've always sort of
said startups need a strong vision. It sounds fluffy and people want to start writing code on day one, but you need to
have a good, strong sense of purpose for your company. And it's so important for hiring and keeping everyone in line and
stuff as well. You need to have everyone on the same page you. You need a page, you know? Often times people start maybe
two or three steps down the path, so they might say like, a lot of people email themselves to-dos, I'm going to fix
that. And I'm like, okay, and I can see how you might have had a brilliant idea, specifically around that, but it's kind
of like what's the bigger landscape that this sits in. Are you trying to change productivity? What do you believe with
productivity that no one else believes? It might be like, oh, I believe it shouldn't be siloed or I believe it should be
a part of everyday life or I believe that you shouldn't be able to take on more than one thing at a time, or whatever.
I'm like okay, well, so we're going to form a basis for a philosophy for you and your problem domain and then we'll work
out what pieces do you think you can uniquely productify. If you know what I mean? As in program and codify. And then
that will form the basis of your product. And maybe that happens to look like your tool that looks like an e-mail
client, but it's actually a to-do list, maybe let's take a step back first. That's kind of the first conversation I try
to have. Let's just appraise the whole environment here and work out what unique thing are you saying.

Des Traynor \[00:41:31\] - When people pitch me on like
a new weather app or whatever, what's your belief about weather? And they're like, oh I just think they all look ugly.
And I'm like, okay, so you believe that beautiful weather will do what? And they're like, I just like designing weather
apps. And I'm like, I thought that's what it was. Maybe you shouldn't be raising around. That's the kind of like the
base of the platform. The next piece I would say to people is you have to be really weary of solving a small, rare,
problem. You can solve a big problem, you can solve a rare problem, sorry, you can solve a small problem, fine. A rare
problem, fine, but small and rare, it just never works. And these products can be effing beautiful, right? What I mean
by this is basically problems in life are either big or small. A big problem might be like, "Hey, me and several of my
friends wants to book a group holiday to Alaska and we have to do blah, blah, and this is a whole big project. I'm only
going to do it once a year, but it's a big enough thing." Okay, fine. You can probably build a product around that and
make some money because there's enough value, it's a big enough problem in your life that if we can fix it, you'll pay
some money or we'll take some commission or something. So that's the size spectrum. Then there's things that happen
every year or things that happen every day. And the things that happen every day typically you'll have a lot of
engagements so the product will bury its way into your life. However, if you have something that no one really

Des Traynor \[00:42:56\] - cares about that often,
sorry, no one really cares about and they don't have that problem often, let's say over the last two years there was a
large amount of apps that are all now defunct that were saying, you know the way Marc Andreessen splits up his tweets?
We'll help you do that. And they designed these typographically stunning products, as in anyone who looks at this will
be like, "Yes, that is a beautiful product. It's a perfect piece of product." It solves a very rare problem that is very
small in nature. And now that's the extreme case, but there are versions of this like, you can imagine loads of B2B
things that happen occasionally and not that big of a deal. Then on the other extreme you've got problems that occur all
the time and are pretty big. Workplace communication, charging your customers money, talking to your customers. It's a
big problem and you do it all the time. They're the places where the Slacks, Stripes and Intercoms can play. It creates
that sort of... No one ever threatens to idly change platform provider or whatever, or payment provider, no you're not.

Craig Cannon \[00:44:01\] - You're locked in.

Des Traynor \[00:44:03\] - Yeah, so that's the next
piece. Intercom might have been responsible for some of this, we deified product so much that people just thought if you
have great product, that's it. The product itself will match with a problem. That's great products match problems. Does
it match with a big problem or a frequent problem? Or ideally a big frequent problem. That's the next big task. A lot of
startups fall down there when they're like, oh, we sync your Facebook to your Instagram and we can do x and y and spits
out a Shopify app. And I'm like, "Yeah, I just don't see it being a problem that often in someone's life." So that's
kind of the next wave. Then there's other little philosophies like, if you're going to charge not a lot of money, it
needs to be self-serve and it needs to be entirely friction-less for the users. And I see a lot of people get what I
call fake-traction where they hand-hold a lot of their early customers doing like the YC-famed call us and install type
thing. But they actually don't have a bridge towards a world where that isn't necessary. And I'm trying to say if you're
going to spend 30 minutes talking to every single customer who needs to install and you've no bigger picture as to how
you're not going to be necessary, you need to be charging more than nine dollars a month. And it sounds obvious, but
you'll find a lot of people who have a very high, let's call adjusted customer acquisition cost when you factor in the
founder involvement and all that, they have a high CAC and they literally have no plan to get away from it.

Des Traynor \[00:45:32\] - Yet, they have traction
because they can point to the nine grand a month that they're making--

Craig Cannon \[00:45:36\] - Because it's working.

Des Traynor \[00:45:37\] - Yes, exactly. But it's not
scalable. And that's another sort of dangerous area. And another example of this might be like, "My product's kind of
good, but I actually learn a lot of free consulting time with me." So like this, okay, I've built a way to automatically
e-mail your customers and as part of the service I'm going to jump in and write all your e-mails. And I'm like, well,
that's what people are buying you. You're a consultant. No, no, I'm a software provider. And I'm like, that's not how it
works.

Craig Cannon \[00:46:03\] - That's dangerous. What about
markets that are growing? Something entirely new. How do you think about that in the context of you know, frequency,
rare, small, big?

Des Traynor \[00:46:14\] - Yeah, so I think it's, I
wouldn't say essential, but it's really, really useful if you're selling in to a growing market. But, everything I said
still needs to apply. The addressable of a market is one variable in the formula here, but ultimately if it's a small
rare problem, it's still... You could have a billion people in the addressable market, it's still the fact that small
and rare means that they're very uninclined to pay any real money. Because the fact that they're in a market doesn't
change how much money they have, right? That's one problem you have there. And then the usual knee-jerk reaction of how
we're going to get out of this, is "Oh we won't charge users, we'll go with ads instead." And I'm like but the ads won't
work, because if it's a rare problem they're not going to launch the app or not going to visit your page a lot. You
don't have the engagement to get the eyeballs to get the actual revenue for your publishers or for your advertisers. In
some sense, it is in some abstract sense possible to have a product that all of the world uses, like seven billion
people use, but if they actually don't care about it at all and it's not important in their lives, they could take it or
leave it, and on top of that they can take it or leave it once a year when the actual problem occurs, it's just not
going to work.

Craig Cannon \[00:47:31\] - They're never going to pay
you enough. There were a couple questions about Intercom specifically and your future goals, so Fossybear on Twitter
asks, "What are your top two growth initiatives for Intercom in the next two years?"

Des Traynor \[00:47:45\] - So I'd love to ask Fossybear
what exactly the definition of what a growth initiative is. I guess the things I'm keen to do over the next two years is
getting our marketing to a place where we are comfortable being slightly more direct. I think we've done a really good
job from a thought-leadership perspective of getting the attention of a lot of people who should use this B2B and B2C,
but I think we need to learn to be more direct and upfront about say, the ROI of Intercom and I think that's an area
where we have a lot of maturing to do. Intercom helps all sorts of businesses deliver multi-million dollar results, but
we never tell anyone that. We're telling people you should love your users and treat them really well and good things
will happen to your business. And that works.

Craig Cannon \[00:48:24\] - Which is true.

Des Traynor \[00:48:25\] - It's true, right? But, I
think at some point as you move up through the market the onus is on you to say basically businesses at some scale care
about two things, how much money they spend and how much money they make. When you're trying to pitch them something,
they just say "Hey, here's my two numbers, which one of these are you changing?" And I think when we show up and we're
like, well if you love your users you're going to stick around, and they're like sh-sh. Don't care about any of that.
Are you going to make me money or save me money? And we need to get better at answering that question. And we need to
have better evidence to answer that question. We need to surface more case studies and we have all the material, we just
need to be more intentional about being upfront about that value. That's one whole area that I'm quite invested in. The
second one for me is the Intercom brand is quite big, we had 1,200 people show up to our event here on Wednesday, we've
had like 6,000 people attend our tour. We have a widely popular podcast, books, blogs, et cetera, but a piece I'm keen
to do is connect the dots a little bit better between Intercom the content phenomena of sorts and Intercom the software.
That's something else I'll be working on. I don't know if that qualifies as a growth initiative--

Craig Cannon \[00:49:40\] - It's a challenge that we have
too.

Des Traynor \[00:49:41\] - For sure.

Craig Cannon \[00:49:42\] - We have things like HN, we
have this podcast, we have our Youtube channel. And I was just talking to Michael Seibel yesterday, we've doubled our
Youtube channel in six months. And that's awesome. How many of those people know what YC is?

Des Traynor \[00:49:54\] - Totally, yeah, totally.

Craig Cannon \[00:49:56\] - And how it actually works.

Des Traynor \[00:49:57\] - Exactly, and we have that. A
lot brands get stuck in this sort of ambiguous place where people know them and love them, but when it comes to shopping
for software or shopping for incubators, they just don't see them in that way. And I think that's a challenge, as in, I
hope it's not, but it could well be the case where there are hundreds of thousands of people who really love YC, but
they when go shopping for the incubator they'd rather go to their local incubator shop or whatever. And it's because
almost in both senses, Intercom and YC, maybe being a bit too demure or standoffish. Come to us when you're ready, but
we're not coming to you. And maybe that suits the brand, maybe it doesn't, but I can see how it's a challenge on your
side of things--

Craig Cannon \[00:50:44\] - Well, I mean, in large part
we're just making stuff that we want and at least me, I don't really consume the super sales-forward content. Even blogs
and podcasts that are all about throwing their brand down your throat, I'm just not into it. I unsubscribe. I just get
out of it. For me that's a thing, but then on the other hand, I'm like okay, there has to be some growth strategy here.

Des Traynor \[00:51:08\] - Precisely, you're the
Director of Marketing, you do want to think that you're actually doing something as well, right? There's a really
interesting spectrum that I often talk to people about when they're in the early stages of their startup, if you were to
say, let's say Y Combinator's product is the actual incubator. It's cash for equity in high potential startups. If you
were to literally only invest on making sure that everyone knows about that, you'll become know as a type of bank or
something like. Oh, "Y Combinator, the financial model?" And if you really drive for that then what happens is, everyone
forgets about everything else and you don't appeal to people under any other grounds whatsoever. It's just like, "Oh if
you need money go to them." And that's actually not your message, right?

Craig Cannon \[00:51:56\] - Oh no, because then we'd be
a commodity, which would be the worst case.

Des Traynor \[00:52:00\] - Precisely, and your value
profit is 50k for eight percent, or something, right? Then then very second you quantify it all like that, something
else will come in and say we're 60k for seven percent. And now you've just lost the fight because you've made it so
quantifiable, you've taken brand and all that sort of stuff out of it, that you've basically sowed the seeds of your own
destruction. On the other extreme, you can have like Y Combinator, the global phenomenona, right? We barely tell you
that we do anything other than just evoke magnificence. And the challenge there is then you're so abstract that no one
actually realizes what you do. And there are genuine big brands that have spread themselves, and I hate to pick on
people, I hate to pick on big brands, but you can think of some of the huge consulting houses or some of the huge
software firms, No one really knows exactly what they do, but everyone knows who they are. And I think that's no use
either, becoming one of the biggest brands in the world that no one can explain for a moment what the hell you do. Or
becoming one of these people that's so associated with you product that you can never do anything else except for your
product.

Craig Cannon \[00:53:05\] - Yeah, absolutely.

Des Traynor \[00:53:06\] - And an example I see is
someone pitches me a startup and it's "Oh, we track tickets for help desks." And what are you called? Ticket Tracker.
And I'm like okay, you do realize that you're basically saying over the next years you're only ever going to track
tickets. Is that like, are you comfortable... I can see how the value is strong for you today because no one's going to
ask you what does Ticket Tracker do, right? And no one's going to be oh, Ticket Tracker, what do you really sell? But
you've sowed yourselves the seeds of your own destruction, because you can't grow that brand in any way. If you're like
Hotels dot com. Well what do you do? Oh well we sell... Okay, that's cool. But not you see like Hotels com and we also
sell flights. And you're like, huh?

Craig Cannon \[00:53:46\] - Totally.

Des Traynor \[00:53:47\] - It's hard to expand a brand
that has a high degree of specificity. It's hard to convert a brand that has a high degree of ambiguity. And that's the
sort of spectrum that we dance in.

Craig Cannon \[00:53:55\] - And how do you connect those
dots effectively and in a way that makes sense for your users? Or would be users.

Des Traynor \[00:54:01\] - First of all, it's like
finding the point on the spectrum that you're comfortable. As in, so Intercom at its core, the idea is it's an intercom.
You want to talk to people. The logo is like eyes and a mouth. You can see and talk to your users. And so our mission is
to make internet business personal. We've picked a relatively abstract point, another version of Intercom would have
been called website messenger. And we would struggle then to sell marketing software or something. For us, it's like
finding the right level of abstraction such that the brand umbrella can cover all of your needs. All of the things you
might want to do. And to do that right, and this is something I would advise all people to do, you need to read up on
concepts like brand architecture and understand the different between an endorser brand and like a primary brand and
what's the difference between a branded house and house of brands and all that sort of stuff. That's all really worth
doing. And then when you've done all that, then it's like okay, so if you're deliberately going for a slightly bigger
thing, you could be selling cheapflights dot com or you could say Aviate, we will take you to your destination. Aviate
is a harder one to convert, cheapflights dot com is a harder one to expand. You find your level and then that tells you
the starting point in your funnel. So our starting point is anyone that has an internet business. From that point, job
one, create an audience of people who are interested in internet businesses and their problems.

Des Traynor \[00:55:30\] - And then job two is then sort
of specify into the problems Intercom solves. We primarily solve go-to-market type problems. It's like sales marketing
and support software. That's basically where Intercom plays. So talk about the problems for those people, we also talk
about product problems because basically in early stage startups everyone does everything, so it's usually the product
person that's also the marketer, you know. First of all grow the audience, then you get the specificity by talking about
specific problems. And by the way, I say talking and my mind goes to content but it's worth saying, this could be media
campaigns, it can be ad buys, it can be sponsorships of events. But basically pushing out the messages that you want and
ultimately get people to the landing pages that represent the things that you want to sell. And then obviously try to
convert them and start talking to them and say, hey, what were you shopping for? This is probably the thing we did most
in the early days of Intercom, when someone signed up we'd be like, "Out of curiosity, what did you think you were
getting when you bought Intercom?" And it was a great question because it helps us unravel a lot of stuff like someone
had a question here, David Kafed asks why did we split up our product? We used to be just one Intercom thing and now
we're a suite of things. That was entirely a result of this. It was basically realizing we were selling Intercom, but
people were buying a help desk. Or people were buying and this was back to Karen's point earlier,

Des Traynor \[00:56:50\] - build what you sell, sell
what you build. So we're like okay, some people love Intercom because it's a great way to support your customers. And
that's one of the most visible use cases and that's why you see it on all the sites. When we meet them like on our
website, we need to let them find the thing they want. So if job one of that is import a CSV of all your targets and
we'll set up some campaigns, "Dude I came here to support my user base."

Craig Cannon \[00:57:14\] - This is a lot for me right
now.

Des Traynor \[00:57:16\] - Yeah, it's like you need to
talk to those folks over marketing, I'm just trying to support people. What we ended up doing is we split up our product
into the things we knew it was used for, which is primarily supporting your customers and marketing to your customers.
And let us be much more specific about when we could pitch Intercom. And then we could say here's what Intercom does for
support teams and then if you sign up for the support product we could say okay, here's the onboarding steps for
support. And we wouldn't talk to you about marketing at all, because you're not a marketer. In the old world we were
trying to charge you and get you to use everything at the same time, so we seemed kind of expensive. And also we were
trying use like a 12-step configuration because you had to everything. And that actually made sense when we were talking
to two-person startups way back, but these days generally we're talking to functions not whole companies. We had to help
people find their own home within the product, so that's where we split the product up. That comes back to that question
as we got more specific, we had to give every single person who's shopping for a different thing, they're own tailored
experience to find the exact part of Intercom they need.

Craig Cannon \[00:58:19\] - Yeah, and so when someone is
shopping on your site, what have been the things that have been most effective in actually converting them right there?

Des Traynor \[00:58:28\] - We haven't done a great
degree of like... I mean there's a certain amount of your listeners you're going to hear well green buttons work better
than red, Craig, did you know?

Craig Cannon \[00:58:37\] - There are 400 shades of
blue.

Des Traynor \[00:58:40\] - The stuff that we found usual
has been un-bundling our pitch into the specific ways in which it's bought, that's been huge. And you can actually see
if you look at say, I think Stripe's homepage does that pretty well these days, they can sell you marketplace or they
can sell you Sigma or Radar or Connect. Similarly, we're like are you in the sales and marketing side or are you in
support side of the org? And if you're in sales and marketing we'll get you a pitch that works for that, and if you're
in support we'll talk to about why you should love your users and how it will increase your NPS and all that. And making
those switches, rather than trying to sell this holistic mishmash that you kind of end up in this one size fits none
phenomena. Getting more specific and getting us a website that enables us to be more specific about our value
propositions for different people, was probably the biggest useful thing. Then second biggest useful thing we've done I
think was tailoring and iterating the hell out of our actual onboarding for the use cases you're buying. All paths don't
necessarily have to go the same direction for somebody to become a customer of yours.

Des Traynor \[00:59:51\] - For some people they might
want to install JavaScript or the people might want to just import to customers and start from there and we've had great
success finding the right ways in which the right types of people can get onboarded to be successful at Intercom. We've
had, I'd say we probably over the years of experimentation before we doubled or tripled our actual conversion rate...

Craig Cannon \[01:00:12\] - Wow.

Des Traynor \[01:00:13\] - Yeah.

Craig Cannon \[01:00:14\] - How man times have you
iterated on the sounds?

Des Traynor \[01:00:16\] - Not enough.

Craig Cannon \[01:00:17\] - Okay.

Des Traynor \[01:00:18\] - Yeah not enough. Honestly it
was something I was thinking about recently. We've been talking with the messenger a bit lately and yeah, it's weird how
like audio doesn't get discussed in software enough because it's not part of the wire frames if you know what I mean.

Craig Cannon \[01:00:30\] - Mm-hmm.

Des Traynor \[01:00:31\] - You don't have the sound
producer in the room with the designer.

Craig Cannon \[01:00:34\] - Yeah it's just an icon for a
sound.

Des Traynor \[01:00:36\] - Yeah yeah. Exactly yeah.
Precisely. So no, you're totally correct. It's something that's on my mind. There's a general sort of tension between
like how identifiable we want Intercom to be versus how customizable it is. And that's another spectrum you have to work
out with users. Like people often want to customize the Intercom launcher and we generally support them in doing that,
but anyone who customize the Messenger we sort of support them in doing that but then they want to customize specific
bits so that it's barely Intercom anymore, and at some point you're kind of like "Whoa. I didn't realize I care about
this but we actually do have some beliefs about how it should perform."

Craig Cannon \[01:01:08\] - Well and it might make it
terrible.

Des Traynor \[01:01:10\] - Yeah, totally.

Craig Cannon \[01:01:10\] - Like there are plenty of
sites where you're like "Where the hell is that sound coming from?"

Des Traynor \[01:01:13\] - Yeah totally.

Craig Cannon \[01:01:14\] - "Why are there bells ringing
right now?"

Des Traynor \[01:01:16\] - Totally. And why is there a
video auto-playing and all that sort of shit. Right, yeah.

Craig Cannon \[01:01:19\] - Yeah, that's the worst. I'm
curious about you in the future.

Des Traynor \[01:01:23\] - Mm-hmm.

Craig Cannon \[01:01:24\] - What's coming next for you
as your role at Intercom changes?

Des Traynor \[01:01:29\] - I would guess- you know,
we're on a scale now where in general, as startups grow you move from like Swiss Army Knives to scalpels, right.

Craig Cannon \[01:01:39\] - Yeah.

Des Traynor \[01:01:40\] - When I was historically like
a Swiss Army Knife with one particularly pointy blade for product. But that was useful because it meant that I could go
and bounce around and take one different portfolios and things and generally bring them up to some level and then learn
enough and then would could bring in somebody who actually knows what they're doing. And that would person would
inherit-

Craig Cannon \[01:01:58\] - You meant burn the house
down.

Des Traynor \[01:01:59\] - Yeah and maybe I've put out
the immediate fires. And I've sort of set the stage for like someone to come in and do some real work. But I think we're
on a scale now where, or maybe I'm unnecessarily optimistic, but I think we have good people leading all the functions.
There might now be a time for me to maybe retreat to an area of actual ability.

Craig Cannon \[01:02:22\] - Okay.

Des Traynor \[01:02:23\] - Which maybe looks like me
going back to the product order. But we'll see. I mean Intercom has never failed to surprise me with the areas, with the
ways in which it can produce new problems for me, let's say.

Craig Cannon \[01:02:35\] - If you weren't working on
Intercom, what would you work on?

Des Traynor \[01:02:39\] - I did answer this once before
and you referred to it earlier. Here's two problems I think about a lot. One of them is simple. It's soccer is without
doubt the biggest sport on the planet. Sorry Super Bowl fans. It's huge. And it is literally the sport technology has
left behind. And I think there's a lot of reasons for that. A lot of them are kind of societal or a lot them cultural.
Nerds and sports tend not to go together. America and soccer tend not to go together, as example ... Sorry about the
recent World Cup.

Craig Cannon \[01:03:15\] - Sorry everyone.

Des Traynor \[01:03:18\] - But there's a huge
opportunity there.

Craig Cannon \[01:03:20\] - Yeah.

Des Traynor \[01:03:21\] - Piracy and soccer is, I would
say, at the levels pre-iTunes, if you remember in the music industry, right, like there is an equivalent of Kazaa as
there are many of them. And no one's doing anything to solve it. Solving it would be a very complex piece of work
because a lot of it isn't programming. A lot of it would be actual code, but there would be a lot of deals and a lot of
business that has to do with partnerships and all that sort of shit, right. And it's not a guarantee. Like ESPN won't
get their shit together or something like that, right. But like I can imagine like for Spotify for soccer, right. As in
"Hey I want to watch that game that happened last night, I should be able to watch it. I'll pay. But it's not even
possible for me to watch a game that happened yesterday. Just not possible." Literally not possible.

Craig Cannon \[01:04:00\] - That's insane.

Des Traynor \[01:04:01\] - That's how backwards it is.
And I think that needs to get fixed. So I think someone should fix that. I think the opportunity is big, the market's
huge. That's one. Another one is I think no one has really taken a harsh look at like, let's just say pensions and
retirement funds and stuff like that, like as in- there's a company in New York called Lemonade that took a really
really nice approach to insurance for property. It's a bot basically. You talk to it and you can get, you can literally
insure your house in New York in like five minutes just through a chat-bot basically. That's an example of tackling a
real, what is historically a lot of paperwork and a lot of fucking around and turning it into a relatively simple flow
and making it work. That model, and I'm not saying chat-bot's aren't the thing here so much as drastic simplification is
the thing, and the Q&A maybe suggests that a chat-bot might be like charming in it's way, too, or at least unique from
a buyer perspective. There's a lot of areas like that where car insurance is an obvious iteration. But anything to do
with mortgage application... There's a lot of areas that are rich for drastic simplification that people turn a little
bit away from because of what programmer call like the schlepp-work side of it. You know it's easier to build a recipe
up front than it is to go and talk to banks about saying I want to reduce mortgage creation to like three taps. But
there are obvious areas where I would have to offer up front as like,

Des Traynor \[01:05:30\] - I don't feel a drastic
passion in any of those myself, but there's something I could get excited about. When I say I don't feel a drastic
passion what I really mean is I know I talked earlier about having a strong vision for the space and all that, I can
jump to like a chat-bot for mortgage applications, but I actually need to take a step back and be like, "What do I
actually believe here?" And it's that I believe I guess maybe that finance should liberated of the bureaucracy that's
been inherent in the industry for so long. You know but I need to go and draw that whole landscape and then be like, "Am
I excited to put another decade of my life onto something like this." Because like Intercom, or the Intercom story has
taken a quarter of my life so far, and I've enjoyed it, but if I was ever to do something else, I now know how many, how
high a filter I have to acquire in order to say yes, right.

Craig Cannon \[01:06:15\] - But it's a huge problem. I
suppose many of these are rare in your lifetime, but they're gigantic.

Des Traynor \[01:06:21\] - Big huge, yeah, big, rare.
That's a great point. That's a great application of that, yeah.

Craig Cannon \[01:06:25\] - Yeah. And I think the
incentives also aren't aligned. Right? The companies are incentivized to make it complicated because they exist on fees.

Des Traynor \[01:06:32\] - Mm-hmm.

Craig Cannon \[01:06:33\] - I think that's why Vanguard
was such a success, right?

Des Traynor \[01:06:35\] - Precisely. Yeah.

Craig Cannon \[01:06:36\] - Ready, index fund.

Des Traynor \[01:06:37\] - Yeah.

Craig Cannon \[01:06:38\] - You're done.

Des Traynor \[01:06:37\] - Yeah. You're totally correct,
yeah. There's a simplification model there and the efficiencies you get by not having to go through all the bureaucracy,
you could share that saving with the user in a sense.

Craig Cannon \[01:06:37\] - Yeah.

Des Traynor \[01:06:52\] - There is an opportunity
there. I'm very confident of that. There's a bit of calculus you have to do to work out where you're going to make your
money and what's the best way to do it, et cetera.

Craig Cannon \[01:07:03\] - That's a whole category of
startups that are just now in the past couple years being attacked. Because in the past it was like, "I'm going to just
make developer tools and stuff."

Des Traynor \[01:07:11\] - Yeah. If it's just me and my
editor it's a lot easier. What is interesting is people probably in best position to do it don't necessarily have the
programming skills. I could imagine a world where like in some universities et cetera, we're going to have our MBAs meet
our engineers and we're going to throw a load of problems in the air and we're going to see what the fuck happens. And I
could see that working. You know, I wouldn't rule it out.

Craig Cannon \[01:07:32\] - The last question I have for
you is you've written all this content over the years. You've done podcasts, Intercom's all over the place. What's your
favorite thing that you've ever made?

Des Traynor \[01:07:44\] - I'm supposed to say Intercom.
I can hear my fucking comm's team in the ear already saying something ...

Craig Cannon \[01:07:50\] - Not just a product. It can
be a blog post, a podcast, yeah ... Assume you like Intercom.

Des Traynor \[01:07:55\] - Yeah. For sure. Okay so let's
just take that off the table. For me personally the thing that would be a Des Traynor production of sorts ... I didn't
know at the time, but I gave a a talk in Boston maybe five years ago, six years ago, called "Product Strategy Means
Saying No" (link). And it was kind of being like ... I'd say, it's definitely the most popular talk I've ever given
because it's seven minutes. And I think it was funny. It was done in the style where I had no control over the slides
and they change every fifteen seconds.

Craig Cannon \[01:08:32\] - Oh it was one of those.

Des Traynor \[01:08:33\] - It kind of forces you to be a
little bit dynamic and entertaining. But it came out pretty well. It was shit in rehearsal. I was convinced it was going
to be terrible. But it came out pretty well when I actually performed it for real. It kind of raised my profile
substantially as a public speaker, and sowed the seeds of a lot of future things, like I got to speak at like 8,000
person events and stuff since then. But I think that was probably, that's really the one that I look back and sort of
choke a little bit because it wasn't like I intended that to happen. But kind of forced into a corner. Like I've always
been ... My makeup is that I'm better under time pressure than I am under like longitudinals or abstract projects. And
that was when I was "Shit, I have to do this thing in the next seven minutes." You know, I was like let's just get
going.

Craig Cannon \[01:09:23\] - You just turned it on.

Des Traynor \[01:09:24\] - And I kind of backed into a
corner. That was what it produced and I look back at that now and I kind, I have fond memories of it.

Craig Cannon \[01:09:31\] - That's cool. Yeah we'll link
up to it then in the podcast transcript.

Des Traynor \[01:09:35\] - There's a blog, yeah there's
a supporting blog post as well. But yeah it was definitely some of the more fun stuff I did.

Craig Cannon \[01:09:40\] - Awesome man. Well thanks for
coming in.

Des Traynor \[01:09:42\] - Thank you so much, Craig.
It's been great to be here.
