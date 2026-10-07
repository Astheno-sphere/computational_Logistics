# How to build a product with WhatsApp co-founder Jan Koum

**Author:** Jan Koum
**Type:** Video
**URL:** https://www.ycombinator.com/library/7a-how-to-build-a-product-with-whatsapp-co-founder-jan-koum
**YouTube ID:** s1Rd4UShDxQ

---

Jan Koum, Co-founder of WhatsApp, shares his journey building his company.

## Transcript

Today's speaker, we have Jan Koum. Jan is the founder of WhatsApp. Whatsapp as we mentioned in earlier iteration of this is the startup
that did everything right. After not getting, after trying
to get jobs at Facebook and not, for either Jan or Brian,
they put their heads down. They figured out a product
that people really wanted. And while everybody else in
Silicon Valley was going to conferences,

doing PR,
whatever else it is that people do, other than making a product
that people really love. WhatsApp just quietly built
this thing that was used by, how many people at the time
of the acquisition? >> 450. >> 450 million people for a consumer app,
and more than a billion now, and it was acquired by Facebook
a couple of years ago. And Jan can tell that story. But that you very much for
coming to talk to us. >> Sure, thanks for having me. So when Sam asked me to come and
speak here, I think I made some smart-ass comment how I'm going to speak about like
people actually building a product and

not going to class or something like that. But as Sam mentioned,
we were just fortunate in a way that we stumbled into something
that people really wanted. And I'll explain in
a second how we got there. But the credit really
goes to not necessarily us having some brilliant idea. I think the credit goes to also being
in the right time and the right place, and building a product that people wanted.

And just realizing that people wanted it. So just to kind of give the quick
history of how we got where we got, we actually, both me and
my co-founder Brian, we were Yahoo for about, I was there for 9 years,
he was there for 11 years. And that time was actually really,
really valuable for us to learn how to scale back-end servers,
what makes a good product, what makes a bad product and
kind of seeing the Yahoo as a company

get really successful and
then kind of, you know the story. So we left in 2007 just coincidentally we both left around the same
time within a month difference. And we took some time off,
we took about a year off. So we left at 2007, we took all 2008 off. He moved to New York with his girlfriend,
I was just goofing off and I really fell in love with my Nokia phone. I had this candy bar,
I think it was 6610 Nokia phone.

That I jailbroke, I installed a net mon
software on it which showed you which mobile cell you were connected to, and
all this advanced things you could do with a phone, that you couldn't do
when you took it out of the box. my birthday was coming up in February, and I figure I'll get myself an early
birthday present, I'll go buy an iPhone. So I went to Apple Store,
bought an iPhone and right around the same time SDK came out,

I think there was no SDK when
iPhone first came out in 2007. But I think they released it at September
of 2008 so I was like literally three, four months after iPhone came out. Sorry, after iOS SDK came out, I got
an iPhone and I started tinkering with it. I was also really bored and
I had a lot of free time. So I'm like okay, well, let's install
this weird thing called Xcode, luckily I had a Mac. Let's install Xcode,
let's figure out what can be done. Let's build a simple app, and
then you kind of realize, holy ****.

It has full Internet connectivity and
it can do full TCP/IP stack. So it basically is a little computer
that can talk to your server. So I'm like, okay, cool,
what can we do with it? So the first thing that we built, which I don't know how many of
you know the history of WhatsApp. The first thing that we built was
actually this concept of a status. And so the idea was if you ever used,
and you all might be too young for this. If you ever used something like AOL AIM or
ICQ or IRC or any of these products,
you have this concept of a status.

Like Yahoo Messenger has this away from
keyboard or I'm busy or I'm in a meeting. And so the first thing that you would do
when you used those messengers is you would like, the first message you
would send was, hey are you there? That was like the first message you sent
to start a conversation with somebody on like ICQ or
if you private messaged somebody on IRC. Because people would be away and so they
would the status to kind of indicate like, I'm not near a computer or
I'm AFK or whatever. And so the idea was like, well,
let's take this concept of status and

just apply it to your phone. So before people call you,
they can check your status. Maybe you're busy, maybe you're in a
meeting, maybe you're traveling, whatever. So if you don't pick up,
it lets people know why you don't pick up. And that was kind of like
the WhatsApp 1.0 application. And what we built was, the app that
hooked into your address book. So the other thing that kind of
worked in our favor was there were Address Book APIs on a mobile phone.

They didn't really exist on a desktop,
right. If you think about desktop like
Windows from 2000 to 2008-ish, people never really put address
books on their desktops. People always had address
books on their mobile phones. And so even if the API existed,
there was like nothing to query because the address book database
was empty on all these devices. And so luckily,
the one thing that Apple opened was their address book APIs,
which was great for us.

So what we did was, sorry, we basically
went through the address book and we could figure out if the contact in the
address book was another WhatsApp user. And that's basically
how the status worked. We would take your phone number, and
if it was an international phone number, we would try to normalize
it to the plus format. So your phone number would start,
all the phone numbers in our system, would start with a plus in
the full international format. And we will be able to do that if
the other person is a person on a WhatsApp network, a user of our product.

And the idea was that,
before you start a phone call, or before you send a message, you would check
the status of this person from WhatsApp. And they would say, I'm available and
you would call them. Right, so, that was WhatsApp 1.0, it failed horribly,
it was a disaster, it was depressing. Nobody used it, people downloaded it,
actually, surprisingly enough, and I think people downloaded it
because there were no apps at the time. There were like maybe 1000 or 2000 apps in the whole App Store
because it just went live.

So we benefited from being early,
but the idea wasn't so great. So people would download and
they'd just like never use it. People just called people
like they normally would. It was really hard to
replace a native dialer, and that's kind of what we wanted to do. We wanted to replace a native
dialing application. So we We struggled for a little bit, we kept adding all
these weird features in retrospect. Back then we thought they
were the best thing ever. You could set your status to automatically
change at a certain time of day.

If you knew you were always in
a meeting from 2 to 4, you could automatically configure it to always say
that you're in a meeting from 2 to 4. So it kind of had that functionality. And then something happened around
the summer of 2009, Apple introduced push notifications so back then if you
wanted the application to wake up, the only way to wake up was the user
tapping on the application item. And there was no way to do anything in the
background which in retrospect was really back words because I do not know if any
of you know about Nokia Symbian phones. Well, 60 blackberry had over capability.

Even before iPhone came
out to do auto start, to do background multitasking,
to do networking, to do all of the stuff. And so IoS actually limited what
we can do, so we're struggling. And then Apple introduced Push
notifications were like, hallelujah. So we ended up,
who came into Apple push notifications? I think this was like
around the summer time. Even before they were still in beta
because we have developer access. And we noticed that people were
using of this status as a way to kind of communicate with each other.

They would change the status to
say like I'm going to a bar. And like the change of status
would like broadcast and go to all the other people who used
WhatsApp in their address book. And so around the summer of
2009 we're like, interesting. Maybe we should build messaging. And then it all kind of clicked
because I've always used SMS. And if you remember on the old Nokia
phones, the SMS was not threaded. So you would get a message,
it would show up with a phone number. And if you get another
message from that person,

it would show up as just
another entry in your list. And then iOS came out and they introduced
threaded SMS, and everybody went wow. So we said okay, well, we can do
full networking, we can do TCP/IP. We can connect a phone, if your phone is
a client, to a server on the back end. We already had all this code to figure
out if you're a WhatsApp user or not. We could take your phone number parse it,
figure out all the international prefixes. We even figured out Argentina at some
point, which was not an easy thing to do,

but we got there. So, we got to a state where we
could actually send messaging, have people send messages over WhatsApp. And, if you look at our application today,
you see all those features. You see group chat. You see ability to send media, to record
voice messages, to do all the stuff. We didn't have any of it. We didn't have like, the only thing
we had was one on one messaging. That's it.
Just think how antiquated that is. And that's what we launched with. So, around September,
I think it was Septemberish,

maybe late August early September is,
a maybe when early October, actually I don't remember is one of
the launch messaging and it took off and it was intuitive to us why it
took off because a semester is so expensive back on those days right and
especially international semester. So if you had two people who were
living in two different countries, how did they communicate? Well, they could send each other SMS,
which was expensive. They could use Skype, but
Skype mostly worked on a desktop, so you had to like synchronize the time when
both of you are in front of a computer,

and, you know, people usually are not. Like, some of you have computers open,
but if you get a Skype call now, you're not going to answer it, right. So, there was really no good way for
people to like communicate in real time. And so that's why SMS was so popular
because your phone was always with you, it was always in your pocket, it was always no matter where you
want your had your phone with you. So when you sent an SMS,
you never said, hey are you there? But you never did that. You'd just send an SMS. The only thing sometimes you could say is,
hey, did you get my message. Because SMS was so unreliable,
especially internationally.

And so that was the other
problem that we could solve by building on top of TCP/IP is that we
could add reliability in our protocol. So, we rolled out messaging. We made it super reliable. We added all these visual indicators. We, if the message actually was
successfully delivered to our server. You knew if it was successfully delivered
to the device that you were sending it to, and it just took off. And, when Sam talks about like,
well, we kind of like When has down. Or we didn't go to conferences and when they didn't do a whole lot of other
stuff, it's just because we were lucky.

We stumbled into something that
people really, really had a need for. Just think about as a mess,
back in 2006, 2007. Right? There was no iMessage,
nothing else worked on your phone. SMS was expensive. It was horrible limiting, you can
only send 160 characters at a time. And if you sent a longer message,
it would break it into multiple chunks. And sometimes the chunk at the bottom
would arrive first, so you'd have to read the message at the bottom and
then read the message on top after that. Media was horribly expensive and
it was not working well across platforms.

So if I sent a video recorded on
Nokia phone to Blackberry users, it probably couldn't have watched it. Or if you send a video recording
on Blackberry to iPhone probably wouldn't work either. So we had all these limitations that meds
we're trying to address in our product and obviously the biggest problem was cost, meds was very expensive in Europe and in
many countries outside of North America. And we just kept going. So once we figured out
that there was a need for it, we were like well, we better hire. So we hired some of our
old friends from Yahoo,

who left Yahoo,
some of our ex-Yahoo friends. I hired a friend of mine who I actually
met when I was working at Stanford like when I was doing IT at graduate
school of business in like, 96 97-ish, when I was in high school, so he came and
he helped work on the Blackberry client. So our goal was like,
we got to build all these features, but we also gotta build all these platforms. Because we started out with iPhone, but
the world back then was very different. Nokia actually was majority
smartphone platform back in the days.

Not in North America, but if you kind
of looked at the rest of the world, everybody was using Nokia smartphones and
Blackberry. And Android, I think didn't even exist. It was just barely existed in
the end of 2009 and early 2010. So we had to build for Nokia, and we had to find people who could
actually build for Nokia Symbian S-60. And we had to find those people in Europe, because nobody in Silicon Valley
even heard of Nokia. So they went and found two really
good engineers to help us build that. Finally, a story about our Nokia client.

It's actually built using Python. Not all our people know that actually
Nokia 60 has Python runtime. So remember when Brian, my cofounder,
started looking at Nokia. Because we knew that we had to do Nokia,
so he kind of went away for a week. He comes back a week later. He's like,
you're not going to believe this. You can use Python to build a client. And I was like, no way. Get out of here.
He was like, no, no, no, no. Seriously.
You can run Python on this little tiny phone. I was like okay let's try and
do it and that's what we did. The basic was the whole back end,
the communications and

protocol was all in Python and
the UI was actually in C++. So we started working on
building multiple platforms and we started working on building features. So we launched Blackberry,
we launched Nokia 60. We launched Android all within
the two months of each other in 2010, and then we started building features. So, we had to build what
people asked us to build. People wanted group chat. Everybody's like, this is great. I love your product. I want to have a group conversation
with my family, or three friends,

or five co-workers, or
ten people in a study group. And we're like, okay,
well how do we build group chat? Let's figure it out. So we'll sit down and sketch the user
experience then figure out how to make the back-end system work for group chat. And then people wanted, obviously
very quickly we added multimedia. And I think multimedia is what
really took us to the next level. Once we added ability to send a picture,
which. Today is like comical, how could you not
have the ability to send pictures through a messaging product over your smartphone?

Back then you couldn't there was
nothing that worked really well. What was cheaper was reliable. So we added the ability
to send the picture, we added the ability to send videos. We at some point introduced voice
messages and then things just took off. And so at that point it was
just scaling the back end. And this is where it
kind of ties into what I was talking about earlier where me and
Brian worked at Yahoo. Because we spent so much time there and
because we were there in early days and we sold the company scale, we had all
this experience to scale the back end.

And we had our own share of outages. And our service wasn't 100% perfect but
we would make sure that we would learn from an outage and make sure that we
would add the right monitoring in place. And we would have capacity always for
holidays like Christmas and New Years where there's a traffic spike. But having that experience
working at Yahoo, learning how to scale
the back-end systems. Learning how to tweak
the operating systems, the kernels, the networking stack. The ethernet driver if you have to,
it's all kind of tied together. So our experience at Yahoo,
our experience with difficult or

challenging SMS protocol that we all use
as a consumer kind of all combined with this perfect timing that happened in 2009,
2010 with smartphones coming online and people wanting to have this
ability to communicate. And if you think about smartphone, the messaging is a killer app for
the smartphone. So we just basically stumbled
into this killer app. Because nothing else you do more
with a smartphone that communicate. Most of it is probably talking to your
friends and family and your loved ones. I message on WhatsApp or
Skype or anything else.

Yes?
They guy [INAUDIBLE] >> Would you do it again? >> Could you make another
app that takes off? >> A messaging app or just an app? >> Just any app? >> I could. I'm not sure you can. >> [LAUGH]
>> I already did this once. I mean the chances of me being
successful again are like zero. So the odds are on your side. So you should go and do something. So that's why we're able to
actually spend all of our time heads down building a product because
we had this amazing product market fit.

We had this amazing product
that people wanted. They were like, give me, give me, give me,
when we were all in and out Nokia S40 which was just like a step below Nokia
S60 Which was kind of a picture phone. People were emailing us, asking for,
when is it going to be done, when is it going to be done,
when is it going to be done? And so,
there was a huge pent up demand for any platform before we would launch it. And so that why we didn't have
a need to go to the conference and do a lot of PR or do anything like that.

Because we had people who needed
our product and we had like millions of people who were waiting for us
to build a new feature or a new platform. And that's why we were able to just
go heads down and build a product. So that was kind of like some background
that I wanted to give you on how we got started. We can do a q and a for
the next 15 to 20 minutes and yeah. >> The specific thing I want to hear most
about is how you dealt with the launch of iMessage and Facebook Messenger and
all the other messaging platforms.

WhatsApp was clearly first, and
then the world got scary quickly. How did you think about that? [UNKNOWN
>> So, how do we think about imessage and all these other platforms. So, with iMessage we,
when did they launch? I think 2011 ish. Something like that. I think 2011 at the developer conference. So, the world in Silicon Valley is
very different from the world outside.

So in Silicon Valley if you look around,
90% of people have an iPhone. Not only do they have an iPhone,
they have the latest, greatest iPhone. Outside of silicon valley,
it's like 80 or 90% Android, right? So for us, having an iMessage launch was
just like a small blip on the radar. >> [INAUDIBLE]
>> So Facebook Messenger so I think Facebook for a very long time
didn't really have a good messaging story.

I remember they bought this company called
Beluga which I think it was Beluga that was group messaging so they were kind
of focused on group messaging at first. And then they shut it down and
turn it into Facebook Messenger. But Facebook Messenger was
part of the Facebook app. It wasn't really a dedicated
app back in the days. But ultimately, if you look at
a Facebook Messenger, the graph that the Facebook Messenger is using is very
different from the graph on your phone. And if you think about people you add to
your address book and people on Facebook,

there is going to be some overlap but
the most part is going to be different. So people who I add on Facebook are
probably not people I'm going to message with a lot. And people who I put in my address book,
people who are probably a different graph in terms of like
how they are important to me and if I urge you into my, basically if
I exchange my number with somebody, it means that you give them the ability
to WhatsApp me, SMS me or call me. There are probably of people who are I'm
friend with in Facebook who called me,

I will probably like, who is this, yeah
we met each other once and I added them. I'm probably not necessarily
a typical example. I mean, I'm sure there are people who have
different grabs on different networks. I'm sure there are people who
use WhatsApp only for work and they only have their coworkers on
the WhatsApp, in their address book. And i'm sure that there
are people who only have certain set of their
contacts in one or the other. But I think overall this idea of like
well if I add you to my phone I give you

permission to interrupt my life is what
makes our network a little different. Because people have these connections that are stronger with people who they
have in each other's address book. With Facebook,
I have people I went to high school with, I have people I went to university with. And it's great that I can keep in
touch with them on Facebook but I wouldn't want them to call me out
of the blue at 7:00 pm it would be awkward because I haven't
talked to them for years. So the graphs are different
in that sense so

we always had kind of going back and
generalizing it. We'll always have competition
from day one, there was actually a point in time where there was a new
messaging app popping up like every month. And every month there was
an article on Tech Crunch how this awesome new messaging app was going to
take down all other messaging apps. And I don't know if they paid
Tech Crunch to write it or what. [LAUGH] And we would just read this and
we would go like, they have no users. How can you write that
story in Tech Crunch. It just makes no sense. And obviously we didn't want to say
anything because we didn't want to draw attention to ourselves.

But actually on purpose tried
to stay under the radar. It was trying to see this from
the sidelines, all this kind of like, dog and pony show that
happened with all these apps. I mean there was ping me, there was
message me, there was group me, there was skigs, there were like, hello, there were
like ten different messaging apps at some point, which kept getting all this
publicity and we were like good for you. Have all the publicity you want,
we'll just stay under the radar and not have any attention drawn to us.

So we'll always have competition be it big
guys like Imessage of Facebook messenger, be it little guys like kick. We always have competition. Even today we still have apps like
Telegram out there, and Line, and Cow. But we said that our destiny
is really in our hands. We can't worry too much about competition. We have to worry about our product and
our users. And if we spend a lot of time
thinking about competition and looking at competition,
we're going to fail, yeah? So trying to build on what you just
talked about, this social graph.

I mean, I feel like this whole
social graph is actually now changing like I mean,
at least among me and my friends. I think I don't call people so much. I don't really send them SMS. I will probably at people mostly on this
social media, like online, Facebook. I could add that or like chat apps
like it's what said it more, but if you feel like this
whole social graph and this social changing slowly because people
call less and people send SMS less. People like to do it more on
this social media platforms.

Do you have a view on that and do you think there's any
like opportunity on that? Or do you think this
shift is even true or? >> I think, yeah, I think true,
so the question was, how, so the world is changing,
people call less, and now like people add the social networks
all kind of merge into one now. Yeah, you're right,
I think people call less these days, and people mostly message each other.

I don't really know if we would
do anything differently today, or even back then. I think for us, the focus has always been
on well, we want to provide a utility, we want to provide an application that
is purely, only about communication. So if you look at some other
apps like V-Chat or Line or Kakao because they do a lot
of different things, right? You can like order taxes through V-Chat
and you can follow people online, like Line has a whole feed concept. And we always wanted to build something
that is really, really efficient and

utilitarian and also fast and reliable. I mean, not a lot of people can have the
latest and greatest smart phone, right? A lot of people have android
phones that are low end. A lot of people have, or
used to have Blackberry phones that didn't have a lot of horse power and
a lot of memory and a lot of CPU, so for us it was always about reliability and
efficiency of the app and not trying to do all these different things that a lot of
different social networks and apps do. Yeah? >> How do you think about Messenger right
now, because now that Messenger integrated

a lot of the features that's WhatsApp had,
I am starting to use Messenger a lot more. And that definitely takes away
from the internal WhatsApp, so do you have internal competition? >> No, I think internal there is still
a lot of room for both apps to grow. I think messenger is really strong
in countries like North America, like the United States for example. So I think they compliment
each other geographically. So I think if you look at countries
like India, or Israel, or Hong Kong, or Germany, or Spain.

WhatsApp has really strong
foothold in those countries and I think if you look at
something like Australia or North America you're probably going to
see Messenger do really well. So a lot of it is also not
necessarily split by a graph, but also by the country you're in. Okay. >> I appreciate the humility that you
couldn't do it again with another app, but I'm sure people asked you
all the time for help or advice. How do you determine if you're on idea or look at an application
it can do really well? How do you think through that?

>> It's very simple. The question is how do you determine if
an app has a potential or is a good idea? It has to solve a really basic problem and
it has to do it in a really simple and efficient way. I mean going back to what we built,
we in some ways solved a problem, right? People had a problem communicating when
they were not in the same room, when they were in different cities, or in different
countries, or in different time zones.

And so,
it's not that it wasn't impossible. It was just, it was hard, and it was expensive, and
we made it easier and cheaper. And when you offer something
to people that is easier and the cheaper people of course, will use it. So I think it's the number one thing to
look at for me when I look at a product, does it solve a need and does it solve
a need on a global scale, right? If you solve a need for
people on Stanford campus, that's great, but can it scale to
a billion or 2 billion people.

So we need it for the only people only in
Silicon Valley by providing them charges for their Teslas, great, how many
people have Teslas in the world, right? It's gotta be a global, actually a lot
of people have Teslas, I don't know. >> [LAUGH]
>> But it's gotta be a global solution that applies to everybody in
every country potentially, right? And so, that was kind of like. >> [INAUDIBLE] Sorry to get
wrong as instead Silicon Valley, everyone's got the iPhone 7S or
whatever we're on now. How did you build that into the culture of
the company to think about your users all

around the world? I don't know. We got lucky with the people we hired. And that was the other thing that I didn't
mention that I should've mentioned. We ended up with a really
incredible team that we mostly hired out of our personal network
from ex-Yahoo and from friends of friends. I think ourselves had
a really good understanding. I mean me and myself being an immigrant
and growing up in other country and

going to all these other countries, I understood that there was more
to smartphone than just iPhone. That was the thing everybody talked
about and wrote about in 2008 and 2009. It's like for me, especially as
somebody who really liked Nokia phones, before Nokia went out of business,
I was like, We've got to build for Nokia, because they're great phones, and there
is like a billion smartphones out there. So I think, just me and my co-founder,
having that perspective,

probably just goes through the company,
and people understood that. Hey, you don't want to just build for
iPhones. You don't want to just build for
the latest and greatest. You have all these millions of phones
out there, billions of phones out there, that you've gotta build for because you
want those users to be using your product. And they also are asking us to do that. Yeah?
>> Can you talk about the business side as far as incorporation,
equity and raising money? A business side my favorite topic, sure.

So we incorporated on my birthday
on February 24th of 2009. And the reason like the thinking that
was going through, so let me back up. We were trying to submit an app
into the Apple Store and I didn't want to do it under my own name. I didn't want the app to say
you Coon because I figured like who would want to submit
an app made by some guy. So I figured we should
probably be more official, we should have a company,
okay, so go to Google. How do you start a company,
right, it's just step one.

So I got a friend of mine,
he was an insurance broker, so he had his own company and he was like 3 blocks away from
me in Santa Clara where I live. And so, I went to his office because I
used to buy insurance for my car and my house from him and so, I was like dude
how did you incorporate he is like it easy you take these articles on corporation
it's like one page was like five things written and you go to San Francisco
to the State Building, the secretary

of the state or whatever and you give
them $100 and they stamp and you're done. I'm like no way it can't be that easy,
he said yeah, it's that easy, I'm like all right, so we had to submit
an app and they wanted us to show. Like Apple Store actually
wanted us to send them a copy of the incorporation articles. So it was like, okay, easy. I have nothing to do that day,
I'll drive to San Francisco, get lunch, go to his office, get a stamp,
Get a letter great. Send it to Apple. They look at the letters,
like yup, you're legit, you're a company, you can now
submit under the name WhatsApp.

I'm like cool. Submitted an app under the name WhatsApp. So that was how we incorporated. In terms of, in terms of,
it's easier than it sounds, like a struggle for me,
because I've never done it. How did we think about money or
the whole funding thing. So we left Yahoo with some savings, because Yahoo did really well in late 90s,
early 2000s. And so we had stock,
we had options, we had our issues.

And so I was actually able
to not only take a year off, obviously not do anything extravagant. But like live off my savings for a year. And then I had enough money to where while I was still tinkering around with
an app and we didn't have exuberant costs. I actually remember like when we started
out I was using my buddy's server, this guy Chuck,
who also used to work at Yahoo. He used to run Yahoo Sports. So I used to sit next to the Yahoo
sports teams, so we became friends. So I was like hey chuck
can I use your server?

I don't want to pay 20$ a month for
a server, he's like yeah sure. So like you know, saving $20 a month
on a server was a big deal for me. So we would run original on his server. And I remember at some point
launched messaging and I saw all this growth and he's like
dude you got to get your own servers. I'm like no I don't want to pay for
my own servers. No you got to get your own servers. You're taking up all this CPU and
bandwidth. I'm like no no no I'm fine. So eventually he kicked
me out of his server. And which was great because we
were switching from Linux to

which would allow them to
have the experience at Yahoo. And so what we were able to actually,
for a long time live off of our savings. And since we had all of this experience on run the company
efficiently when it comes to servers and backend and bandwidth and everything,
there was not a lot of expense. The expense started when
we had to go hire people, and the idea was that okay,
we going to have to pay for bandwidths, we going to have to pay for
Banbros, we going to have to pay for SMS verification because to sign up on
WhatsApp you have to verify your number.

And, we did a small angel round, I can't even remember,
I think it was end of 2009. We did a small angel round, and then we basically kind of kept our company
running without losing too much money, because in the early days,
iPhone app was actually paid. The people had to pay one
dollar to download iPhone app. While everything else was free like
Android and Blackberry and Nokia. And so we had people paying for
iPhone app and that kind of went to,

it gave us the ability to pay for the
bill, for electricity for bandwidth bills, for several bills and all that stuff. And I think probably around 2010, 2011. People started knocking on our door. We didn't even went out to look for money. Which is a great situation to be in. because if you are going to go raise,
and you need money, you probably are not going
to get the terms you want. Which was, for us was,
kind of worked in our favor because

all these receipts started
coming to us and they're like. Because they're doing great we want to partner with you
we want to give you money. And we're like eh we don't really need it. Which makes them want
to invest even more so we kind of did this dance where we're like
no no we don't really want your money. Come back in a few months and eventually
after all these conversations me and Brian sit down and we're like okay well. We just wasted their time and our time, should we just take funding or
should we not. And we decided we should because it's

better to have money in your bank
account for your business or not. And that's the words of wisdom that I
got from Jeff Who because Jeff was like if you can have money in your bank account
you should have money in your bank account because you never know if you have to buy. In building or if your netted to buy some office space
because you started growing too quickly. And you don't want to negotiate and
raise money when it's too late. Like, you want to do it
when you don't need money. So listening to words of
wisdom of Jeff Ralston, we were like, okay, let's get some
funding and we partnered with Seguin and we got money from
Sequoia Any other questions?

Yeah?
>> Could you sort of walk us through your internal psychology and confidence
over the trajectory of the company? At the beginning, did you identify that
the market timing was pretty spot on, or were you just sort of following
what your users were saying to you? >> I think until we did messaging,
when we doing that status feature, obviously it was rough because we had
no users, and nobody using our product.

And so you're sitting there In
your room building a product and thinking like well, nobody wants to buy. Why am I doing this? What is the meaning of life and
all that stuff, right? And so you kind of like it's stuff. When you're building a product that people
don't really want, you feel rejected. You feel like, why aren't you using it? It's great, I put all my energy in it. So once we added messaging,
it was like 180 degrees difference.

All of a sudden everybody
wants our product. Everybody thinks it's
the coolest thing ever. We get all these letters into
our own email, in-boxes. All these emails from people
saying how great your product is. I'm able to keep in touch with my fiance. I got married because of your product. Your product helped me save lives
because the hikers were lost and the hikers were able to use
WhatsApp share location to send. It's just night and day. When people want your product, and they love your product, the psychology
inside a company is just different. People would come to work, and they'd be
like we're building the best thing ever.

People loves the product. This is great. And so, we didn't really have to do
a lot of selling even to the candidates. Like, people who came in to interview
with us basically fell into two counts. People who live sole bubble and never
heard of WhatsApp and they'll be like, where would I work for WhatsApp? And people who kind of fell into like,
well, there is a whole world out there bubble, and they were like, you guys have
millions of users, like my cousin in Spain or my friend in Germany was telling me
about your product and everybody uses it. Or people would say, I went to India or
I went to Middle East and everybody uses your product. It's like amazing how come
nobody heard about you?

And they're like, well, that's on purpose. And so basically like these two types
of people would with intro and so obviously people who were had it
like the silicone valley bubble. They don't even want to come work for us. Which is not the end of the world because
there were plenty of people who understood there was a whole big world out there. And they were happy to build product for hundreds of millions of
users all over the world. Yeah.
[INAUDIBLE] >> How was the fundraising experience [INAUDIBLE].

Why did I partner with Sequoia? So we had a few companies
give us term sheets. One of them even gave
us a blank term sheet. They're like,
fill out the number you want. >> [LAUGH]
>> And we're like, well, if they're that, that irresponsible with
other people's money, we shouldn't do that,
shouldn't be partnering with that. Sequoia is just an amazing brand, right? For me,
living in Silicon Valley since 1992 and

reading articles, and seeing news about
all these companies that have gone public, like Netscape, and Sysco, and Google, and knowing that a lot of them were backed
by Sequoia just made it not a very difficult decision to pick Sequoia Well,
I also really like people who work there. A lot of it was just personal chemistry. A lot of it is the C company understanding
how much to be hands on or not.

Like Sequoia was actually really
great about, they knew the numbers, they knew we were growing. They didn't meddle, right? They didn't need to come in and
say you guys are doing this wrong or doing that wrong,
there was no need for that. And I think we had that understanding
upfront, where they kind of made us a promise they were like,
we're here to help you financially. We're not here to help
you with management. We're not here to help you write code. We're not here to help you build features. We're here just to help you grow and
to help you financially. And if you need any help outside of that,
come knock on our door and

we'll try to help. And they were really helpful with stuff
when we asked, like recruiting or anything like that. They would sometimes meet with
prospective candidates and tells them why they should join WhatsApp. So Sequoia was really great,
it was a brand. And I remember, actually,
when we have multiple term sheets. Me and
Brian went to Jeff Roston's house and we were talking to him,
it was late in the evening. We were trying to just get
advice on what we should do and he kind of looked at all them. And we talked through
all the different terms. And then he kind of said,
once you're a Sequoia company,

you 're a Sequoia company. It's that branding is really strong and
it means a lot. >> I have an important one. >> Yes, what? >> [LAUGH]. >> [INAUDIBLE] for you, but-
>> How did you get your first few thousand users back in the day and set the status? >> Well, how did we get our
first few thousand users? So, there was no apps back then. And iOS, well it wasn't iOS back then,
it was iPhone OS. And the Apple Store had
this category What's New.

And the trick was to submit
a new app every few days, so you would always show up
on top of What's New. And you would make a small
change to the name. Because I think back in the old days, the name difference
triggered you as a new app. So it would basically have status and then
it would say status for your smartphone, or status for your calls, or status for
your iPhone, or updated status. We would basically tweak the name a little
bit with every new version we submit.

Which always kept us almost always
at the top of the New category. And since there are no apps, people would
go to What's New category all the time to download, to try to download
whatever people would build. Because today you have thousands of apps,
back days you had hundreds. And basically by gaming the system
a little bit, we were able to. I think that loophole got
closed really quickly, but luckily by that time we
already had messaging. Yeah? >> How did you scale up your company,
I mean, how do you scale up WhatsApp
into different countries?

>> How do we scale into
different countries? We didn't have to scale. Well, we did have to do a couple
of things, I take that back. So, there were two things
that we had to do. One, we had to build different platforms. Because there were some countries
where iPhones just didn't exist. And everybody was using either Nokia or
Blackberry or a combination of two. The second thing that we started
doing early on is focusing on localization, right? So again, this kind of goes back to
Silicon Valley bubble where everybody in Silicon Valley speaks English. Therefore, the rest of the world
must speak English, not quite.

So, we focused early on localization. We actually hired people internally into
the company who were doing two things. They were customer support
representatives, so they would help people with problems and
write FAQs and help debug issues. But they were also all multilingual. So we'd hire somebody who
was perfect in Spanish, and we would hire somebody who
was perfect in German. And we'd hire somebody who is
perfect in Portuguese, and we would hire somebody who
was perfect in Italian. We would hire somebody who was perfect in
all these languages where our apps were starting to grow. So we could build a really good,
localized experience.

So when you download WhatsApp in Brazil,
it's not in English, it's in Portuguese. And I think that is what helped
us grow in all these countries. Yeah. >> How did you convince your first few
employees I know that they came from your personal network. But how did you convince them to join you? >> It wasn't hard,
most of them were unemployed. >> [LAUGH]
>> So let me see, so Brian joined, so Brian left Yahoo.

And he, I think, didn't really do
anything, I think he left in 98. So he didn't really do anything for
ten years. He was one of the early app engineers. >> [LAUGH]
>> So that was one. Chris, my friend, who went up to Stanford. I think he was doing this startup
that wasn't really going anywhere,. And he was in LA, and he got married to this wonderful girl
who's parents are actually from here. So, I think for her it was an advantage
to move here to be closer to her parents. So I'm like yeah, yeah, you guys should
move, you guys should move here, move back to northern California.

So the combination of her wanting to
move to be closer to her parents and him not really doing anything not having
a full time job also contributed. This guy Eugene who was one of our early
hires, he was working at a company, I actually knew him through my social
network, we are still friends. And he would always complained how
he hated his job and how there were trying to **** him over by promising
him stock options and never delivering. He hated it, so I'm like, well,
here's a good opportunity.

Let's see what else. We hired this guy Michael who was in New
York, wasn't really doing anything also. So, he was a referral through
a friend of mine from Yahoo. So there was this guy Michael Radman
who I used to work with at Yahoo, who was working at a startup,
and we would keep in touch. And at some point I was complaining to him
how hard it is to find good engineers that are smart and capable and can get **** done and
don't just sit there and theorize. And he was like, I know a guy,
calls this guy Michael in New York. And so we randomly call this guy
Michael in New York, and I'm like, hey,

Michael, I got your name
from other Michael. Do you want to come and interview? And I figured he would say no,
I'm pretty happy in New York. But he wasn't really doing much,
he was like, yeah, okay. So he came in and interviewed. And so we had, let's see. We had one of the guys,
one of our engineers was in Russia, it was this guy Igor. He wasn't really doing
much in Russia also, it's not like they have
Silicon Valley in Russia. >> [LAUGH]
>> So we were like this band of outcasts
in some way, the group of people who weren't really doing much who got
together and built a product.

But there were also people who were
working full time who we actually had to try really hard to convince to join. One of the guys, Rick,
who helped us a lot with the backend as we were scaling the backend,
he was working at Yahoo. And so I think it took us six months
of meetings and dinners with me and Brian trying to convince him. And we would meet him, and
we would do it in a very subtle way. Not like, come join us. We were like, we have all these users and
we have all this gear. And we knew he was really, really
technical and he loved solving problems. So we weren't saying come join us and
we'll give you lots of money or

options or whatever. We were playing a different angle
where we're saying, hi Rick, if you're watching this. We were like, hey Rick, we're having all
these technical problems, and we did. And we're like, we just don't know,
there's this weird issue with FreeBSD 8 where it computes for
kernel resources with Erlang. And Erlang is trying to
run on these 48 cores, and we don't know how there's some
contention in the kernel. If only we could figure it out,
we just need some help. And we knew that he loved doing
this kind of stuff, right? So with him, we played a different angle. It took us a few months to convince him,
but eventually he joined and he helped us
fix a lot of bottlenecks in our system.

So there were all different stories, but
I think the bulk of the initial kind of core of people who joined, they were from
our professional and personal networks. >> We are out of time, unfortunately. >> Man,
I can keep going as long as [INAUDIBLE]. >> All right, if you got
>> All right, we'll go to one more question. Thank you. >> Sir. >> I think what's happening, sir,
role model will get off being focused. I want to understand your decision making
process when you get feedback from users.

How you define its said
noise to your product, how you define,
it's a key feature we need to improve. And how you find out that
the efficiency of communicating is a core feature you wanted focus on for
so many years. >> How do we know what features to
build and what features not to build? And you're absolutely right. Because in the early days, people would
write in and say, we want usernames so we want PINs. Because people were so conditioned by all
these messaging apps that came before us that you need to have a username or PIN.

So if you were using BBM or
if you were using ICQ, you have some random PIN that you
would have to exchange with people. Or if you were using Skype or Yahoo
Messenger, you had to have a username. And people didn't understand
that what we were building was this whole new idea of like you
don't need any other stuff. You just sign up with your number, and it's connected to your phone that
has the same phone number, and you go. And so in early days, a lot of feedback
we took from users was useful. They're like, we want groups,
we want multimedia, we want to have additional privacy controls,
we want to turn off our last seen.

Great, we built a lot
of what people asked. But we also didn't build what people asked
because we didn't think it was the right fit for our product. Having the fundamental belief and the gut
feeling that what you're doing is right, and having that vision of,
it's just going to work. I'm going to build it using phone numbers. I'm not going to have usernames, I'm not going to have PINs because
it makes product more complicated. It makes product harder to use,
people forget their usernames and PINs and all that stuff. Having that belief in yourself, and knowing that what you're building is
going to work is obviously also important.

So that's kind of how we
would make decisions. >> Okay, you go, and
then we'll take that for the 1 PM class. >> Yeah?
>> Yeah. What do you feel about security issue or
future security issue of Messenger app? >> What do I feel about security issue or
future security issue? For us, well, as you know we
rolled out into an encryption. And we weren't the first ones to do it, obviously there were apps before
us that focused on security.

But we were the first ones to
do it on such a global scale for everybody seamlessly, right? I mean there was no other app today that
has more than a billion people that has end to end encryption enabled by
default into everything you do, individual chats, group chats,
and everything else. So, we didn't start out. Again, this kind of goes back
to what we started with. It was just a pure one-on-one messaging,
right? There was no group chat,
there was no multimedia, there was no enter an encryption,
there was no video callings, there was no voice phones,
there was none of that. But over years, we made a commitment to
our users that we were going to add all

these features, and we were going to make
them work, and make them work really well. And so obviously, we feel strong is
that encryption is important and we feel strongly about Internet
encryption which is why we added it and which is why we have it
in our application today. >> Great, thank you so much. >> Thank you.
>> [APPLAUSE]
