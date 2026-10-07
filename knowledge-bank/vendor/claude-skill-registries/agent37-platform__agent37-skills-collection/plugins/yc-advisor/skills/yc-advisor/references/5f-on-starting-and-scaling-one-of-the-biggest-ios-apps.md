# On starting and scaling one of the biggest iOS apps

**Author:** David Lieb
**Type:** Video
**URL:** https://www.ycombinator.com/library/5f-on-starting-and-scaling-one-of-the-biggest-ios-apps
**YouTube ID:** fDcW_qb-uew

---

[David Lieb](https://twitter.com/dflieb) is the Product Lead for [Google Photos](https://photos.google.com). Prior to
working on Google Photos, David was the cofounder and CEO of Bump, which was in the Summer 2009 batch of YC.

[Gustaf Alströmer](https://twitter.com/gustaf) is a Partner at YC.

David is on Twitter [@dflieb](https://twitter.com/dflieb) and Gustaf is [@gustaf](https://twitter.com/gustaf).

-----

## Transcript

Craig Cannon \[00:00\] - Hey, how's it going? This is Craig Cannon and you're listening to Y Combinator's podcast.
Today's episode is with David Lieb and Gustaf Alströmer. Gustaf is a partner at YC. David is the product lead for Google
Photos. Prior to working on Google Photos, David was the co-founder and CEO of Bump, which was in the summer 2009 batch
of YC. You can try Google Photos at [photos.google.com](http://photos.google.com). David is on Twitter
[@dflieb](https://twitter.com/dflieb) and Gustaf is [@gustaf](https://twitter.com/gustaf). All right, here we go.
Welcome to the podcast, guys.

David Lieb \[00:33\] - Hey, thanks.

Gustaf Alströmer \[00:33\] - Thank you so much.

Craig Cannon \[00:35\] - Today, we have David Lieb. He is a Product Director at Google, specifically for Google Photos.
What some people might not know, is you are also the co-founder of Bump. Bump was one of the biggest apps on the App
Store, for the first few years of the iPhone. How did that happen?

David Lieb \[00:50\] - Totally random. I was in business school, I had been an engineer and I kind of went to the dark
side and went to business school in the fall of 2008. This was right when the iPhone had come out a year earlier. They
had just opened up their app store to third party developers that summer. I showed up to business school and I met a
couple people in the computer science department who had built apps over the summer. There was one guy I met, he had
built an app that looked for open WiFi networks and it just told you which ones were open and which ones had a had a,
whatever it's called, a password. He made $200,000 that summer selling that app, I was like, "Okay, we should build an
app here. It'll be fun." At the same time I was in business school and I was meeting all my new business school
classmates and we were doing that thing that like we still, honestly, do today which was, "Hey, tell me your phone
number. I'll type it in. Then, I'll call your phone. You just miss the call, and then you ask me how to spell my name."
One day, I did that 10 times and I was like, "Okay, somebody should solve this and ooh, there's apps now. I could
probably solve it." I emailed a guy I met, I didn't really work with him directly, but I had met at my previous job at
Texas Instruments and I said, "Hey, Andy, any interest in building an iPhone app?" At the time he was like, "I think
Android's going to be bigger." And I said, "Eh, let's start with iPhone. I think it'll get there sooner."

David Lieb \[02:08\] - We just started hacking away and trying to build this app to make it easier to share your phone
number with people that you met. It was a total side project. I was a full-time business school student. He was doing
his own thing. He was in California. We just kind of worked on it for a while. I met my third co-founder, Jake Mintz, at
Business School. He was also just a random classmate of mine we met. We both had worked at Texas Instruments so we
started to talk about that. We brought him on board, and the three of us just kind of did the whole thing ourselves in
our spare time. We put it onto the App Store, and people started using it, we were like, "Ooh."

Gustaf Alströmer \[02:40\] - And this was in 2008, 2009?

David Lieb \[02:42\] - We launched March 27, 2009, was when it got out to the world.

Gustaf Alströmer \[02:46\] - At that time it was very non-obvious that apps are going to be big. I remember watching the
apps the first six, 12 months.

David Lieb \[02:50\] - The top apps were fart apps, silly, trivial things. A lot of people viewed Bump as a silly
trivial thing too, right? It was like this kind of novelty of the iPhone, like, "Oh, yeah, it's got an accelerometer.
You can pump your phone together and it does something." But that actually was the engine that made it grow. We launched
it in March. We got a, people started using it, it was growing slowly, but then because of that novelty and the fact
that the iPhone was a thing in the news. It was around that time. Every reporter wanted to talk about the coolest apps
on the iPhone, and so I remember I met one reporter from the Chicago Tribune at a random business school conference
once. I emailed him and I'm like, "Hey I've got this cool app. you might want to write about it," and he wrote about it.
And then, I did this little hack where I took his article, and I forwarded it to the next-highest person on the
journalism rank, and I think I mailed it to David Pogue at the New York Times. I was like, "Hey, the Chicago Tribune's
got this already, but you could still write about it." And then, he wrote about it, and then I took that and I like went
up the notch and eventually, it just got pretty popular. We were maybe on the 200 on the top app chart at the time that
the billionth app was going to be downloaded from the App Store. Because we were the top 200 app, we were getting a lot
of downloads that day. The probability of us being the billionth download,

David Lieb \[04:11\] - was 2% I think on the day that it happened, and it was us. And so I got a call in Chicago. I was
in Chicago. I got a call from the woman who runs all of developer relations from Apple and she's like, "Hey, good
morning. You were the billionth app downloaded yesterday. We'd like to tell the world about it." But I wanted to call
you to make sure that your servers are going to be able to handle it. And I was like, "Oh, yeah. Let me call you back."
So I called Andy. I'm like, "Andy, are we going to be able to do this?" He's like, "I don't know." And I said, "Okay,
that sounds like a yes." So we just,,, We said, "Yeah, go for it," and that then put us on the map. That was the thing
that got us globally. Everybody heard about us.

Gustaf Alströmer \[04:49\] - Apple promoting you or what happened?

David Lieb \[04:51\] - Apple did a marketing little effort, little marketing effort around it. But then later, after we
joined YC that summer, they actually put us into an international TV commercial. This was the, There's An App For It
campaign people might remember, and we were part of that. We didn't really know we were going to be a part of it. The
way Apple works is they're very secretive. They say, "Would you please sign this waiver that says we can use your brand
in various things," and I'm like, "Okay sure." And yeah, one day during YC we were looking at our graphs, and our
servers just , It was a factor of 1,000 in 10 minutes. And we were like, "What's going on? There must be a bug," and
then our friends started pinging us saying, "Hey, I just saw you during Dancing with the Stars," and I'm like, "Oh,
wow." And that's the point where our servers totally melted down. Everything broke. And this was the first moment where
I realized the value of the YC network. I sent an email out to YC founders, and I said, "Hey, does anybody know how to,"
I think we were using Apache. There was an Apache web server in our stack at the time. And I said, "Is anybody an expert
at this?" They came over to our office and just sat in our desks, and they said, "Step away from the keyboards. We'll
fix it," and they just totally fixed it for us. And so that was the first moment where I was like, "Ooh, YC's really
valuable." I remember when I was talking to Paul Graham about how we should do this and he said, "I won't be able to
explain it a priori, why it's really valuable,

David Lieb \[06:10\] - but I guarantee you'll see that it's very valuable." And that was the first moment where I was
like, "Yep, he was right."

Gustaf Alströmer \[06:14\] - I'm curious about how you got into YC. So did you know about it before? How was the
interview like?

David Lieb \[06:18\] - We didn't know anything about it honestly. Jake and I were in business school. We were trying to
learn about tech because like everybody in business school, you're supposed to go get an internship for the summer and
so we were like, "Oh, where should we get our internships?" We were reading TechCrunch a bunch, and we kept seeing this
thing called Y Combinator and I was like, "What is that?" It turns out we knew a couple people who had gone through it
already, and so we went and talked to those people. I knew Savraj, who had done Wattvision I think was his first one.
And I went and talked to him and he's like, "Yeah, you should totally do it." And so we ended up applying and got in.
The interview process was fascinating to me as an outsider in this world.

Craig Cannon \[06:57\] - Who was interviewing you?

David Lieb \[06:58\] - Our interviewing was PG, Jessica, Robert Morris and--

Gustaf Alströmer \[07:05\] - Trevor?

David Lieb \[07:05\] - Trevor. Yeah, the four them.

Craig Cannon \[07:07\] - I can only imagine. What were their responses when you're like, "Okay, so this is an app that
you share your contact information..."

David Lieb \[07:13\] - It was fascinating. We walked in and we sat down, and literally before I could open my mouth,
Paul said, "Give us your phones. We want to try it." And I was like, "Okay." We hand our phones over to him, and they
just start playing around. RTM was like, "Oh, I'm going to try to hack it and break it. Let's all bump at the same time
and see if we can break it," right? And I do distinctly remember Jessica being like, "So how do you guys know each
other? Tell me about that," and that was the moment where I was like, "Oh, okay, she's interested in understanding how
the founders know each other, what our backgrounds are, what type of people are we," whereas Trevor and Robert were just
hacking away at the tech, right?

Craig Cannon \[07:50\] - Nerding out.

David Lieb \[07:50\] - It was a fascinating moment and the most surprising sentence that was spoken in our interview was
at some point PG just kind of detached and put his head down, and he was kind of just thinking. And he said, "How does
this become bigger than Google?" And I was like, "Dude, are you crazy?" But that just showed how he thinks that you can
take something that seems so frivolous at the beginning and turn it into something potentially that would be really big.
That was cool to see.

Craig Cannon \[08:15\] - That's so cool. And so did you establish a metric early on during YC? What was your goal before
demo day?

David Lieb \[08:23\] - We were really anchored on how many people used it and how many times they used it. That's the
main thing that we were focused on. In hindsight, that probably was not the right thing to be focused on, but I think
especially for us as total newbies to this space, we didn't know anything better. This was actually one of the big
learnings that we had at Bump that we grew like crazy. We got up to 150 million downloads of our app, and I think at the
peak we were at 10 million monthly active users. It was a very big property, especially 10 years ago on the internet.
That was really big, but the thing we were looking at was how many people use it, and how many bumps were happening per
day and per month? And what we weren't tracking as precisely as we should have was do the people who use it today, when
do they keep using it? How frequently do they use it, and what is the retention curve? I remember we were raising money,
and all the VCs would ask, "What's your cohort retention curve look like?" And I would be like, "Oh, it's good," and
then I'd go and Google cohort retention curve. I'm like, "What is that," and I was trying to learn, what is this metric
that people keep talking about? And in hindsight now, I realize it's the single most important thing. With Bump, the
actual dynamic was that our longterm cohort retention was really good actually, if you measured it on a wide enough time
period. Basically people kept it on their phone and they would definitely use it at some point in the future. The
problem was the frequency of use was very long,

David Lieb \[09:47\] - and so we thought that we were going to be able to build a business off of a large user base
using this product but if your large user base uses your product infrequently, you have to figure out a way to extract a
lot of value each time they use it. And for Bump, the value was marginal. It was like, "Yeah, it's nice, it's
convenient. I could solve my problem in another way and it's not that hard." So ultimately, that was the thing that kind
of killed it as a business for us.

Craig Cannon \[10:10\] - Surely you tried things, right? What'd you try to push into before you ultimately decided to do
something with photos?

David Lieb \[10:17\] - We thought about a bunch of ideas like should we just charge for the app, or should we have a
freemium model where there's certain feature set that you would get if you would pay? We tried in-app purchases for
different stickers and things like that. We tested all these things as tiny 1% tests. We tried ads in the product also
as a little test, and we basically concluded we could basically get maybe one million, oh sorry, $1, for every user of
the product per year on average. Then we realized, oh, we've got 10 million monthly active users. That's a nice
business, but it's not a business that you go raise huge amounts of VC funding to go build. That was the point. I think
this was in beginning of 2012 maybe where we realized, "Oh, hmm, we need a better plan," because our plan all to that
point was just grow, grow, grow, grow. Facebook did it. Twitter's doing it. We'll just do it, too, and it'll be great.
And I think we didn't understand the fundamental differences between our business and those businesses.

Gustaf Alströmer \[11:18\] - What made the product grow? What made Bump be so big?

David Lieb \[11:21\] - It was 100% word-of-mouth distribution, so we spent no money on customer acquisition, no money on
marketing. I used to tell this story that the amount of money we ever spent on marketing, I think, was $42, and it was
for me to buy a video tape to put into a borrowed camcorder and a black piece of felt to put behind to so I could make
the demo video for Bump in my apartment. That was it. But yeah, it was all word of mouth. People who got the app thought
it was cool enough that they wanted to be like, "Hey, Gustaf, try it. I want to show you this cool app I just
downloaded." What we thought was going to be an inhibitor to growth, which is this chicken and egg problem, you can't
use it unless I have it, actually turned out to be the, driving force behind our distribution because it was novel and
cool enough that people were willing to take that investment to say, "Oh, then just download it. I'll wait." And that
worked.

Gustaf Alströmer \[12:12\] - And you thought about product-market fit quite a bit. You mentioned that in one of the
talks you did at YC, so we'll come to Flock in a second, but there's three different products you've worked on the last
couple years. When you think about the product-market fit in terms of Bump, how do you analyze today kind of after the
fact?

David Lieb \[12:31\] - Product-market fit, it's a very subjective concept. I don't think you can really measure it
because you can have very great product-market with some customer base, but as you try to expand your customer base, you
might find, "Oh yeah, there's not product-market fit for these other people over here," and so saying you've reached
product market fit I think really is like it's a staged question. Ultimately, if you want to be huge in a consumer
space, you've got to get to a large group people, and the question is do you have product-market fit for that large
group of people. Even with Google Photos today, my answer would be we certainly have product-market fit for a large
group of people in the world, but there's another group of people who use our product that I wouldn't say is
product-market fit necessarily. There's a whole lot more things that we need to understand and build for that. When you
get to a billion or more users, the next person who joins your product, they're very different than the first person who
joined your product, and so you've got to really understand that.

Gustaf Alströmer \[13:26\] - Got it. After Bump, you guys tried another product, so Flock came around. Tell us about
that.

David Lieb \[13:34\] - We built Bump to share the contact-sharing problem, and people started using it for that. Apple
eventually added an API to access photos on the phone, and we thought, "Okay, let's just add that. Let's see what
happens." It's pretty cheap to do, so we added that feature, and people started using that. And it turned out that
turned into the biggest single use case of Bump, sharing photos, and so one day in beginning of 2012 when I was looking
on our dashboards and I'm like, "Oh, I think it's not going to keep growing. What are we going to do?" I thought back to
the advice that I heard PG give us back in YC, which was, "When you're stuck, go talk to your users. They will always
tell you what they want." So I said, "Okay, guys. Give me a list of the top 100 users of Bump in the world. I'm going to
try to go have phone calls with them." So Jake and I that day went into a conference room and just tried to call as many
of those people on the phone as we could, and we said, "Hey, we're the founders of Bump. We just wanted to hear what you
think of it, why do you use it, that sort of thing?" And what we heard was basically most of those people said, "Oh, I
don't use it for contact sharing. I use it to share photos with my husband." And we're like, "Wait, what? You can just
email the photos to your husband. Why do you do it?" And these people would tell us, "Well, it's just easier, and they
get the full-resolution file, and I don't have to worry about attachments and emails bouncing. It's just easy."

David Lieb \[14:50\] - We thought, "Oh," and that then led us to, "Okay, so there's clearly a problem in the
photo-sharing space amongst your friends or family," but the product we built is kind of the most hard product to use to
solve that problem, because both people have to download this app. You have to stop what you're doing and both decide,
"Okay, we're going to do this Bump thing now."

Gustaf Alströmer \[15:13\] - You have to physically--

David Lieb \[15:13\] - You have to physically touch each other, right? When you're building a product, you try to
minimize friction of using your product, and with Bump, it was almost like we'd maximized the friction. So we were like,
"Okay, let's try to build a product that minimizes the friction rather than maximizes it," and so that led us to this
product called Flock that built and launched. It was really a very convenient turn of events where at the same time that
Jake and I were sitting in that conference room, roughly, having that learning or that insight, our engineering team was
developing the Bump algorithm, which was really like a pattern-matching, early type of AI system that would use a bunch
of signals to predict whether you bumped with another phone, because it was all server based. There was no local....

Craig Cannon \[15:54\] - Right, there was no NFC.

David Lieb \[15:55\] - Yeah, exactly. Okay. So it was all kind of like a magic trick, but our engineers said, "Hey,
Dave. I can tell you who's going to bump with whom tomorrow." And I'm like, "How can you do that?" The answer was they
would go look at where and when people took photos on their phones, so they'd look at the metadata of their camera roll,
and they could say, "I'm pretty sure Gustaf's going to bump with Craig tomorrow." There's an 80% probability that they
do. And I'm like, "No way." And what they did is they figured out that today, you two were at the YC office, and you
took a photo, and you took a photo at the same time, and they were like, "Probably, then, you're going to bump those
photos to each other." And so that was the key insight on the tech side that allowed us to kind of marry those two
insights and create this product, Flock. Flock looked at your Facebook friends and figured out when you took a photo at
the same time as when your other friend was there, and then it basically did a suggested sharing prompt

David Lieb \[16:49\] - to you to say, "Hey, it looks like you might want to share this photo, and just press this one
button, and we'll share the photo to the other person." We built that app. We used it ourselves. We used it with our
friends and family before we launched, and we realized wow, this is really great. It just makes my life so much easier.
I'm getting all these photos from my friends that I was never going to get otherwise. And then we launched it, and
nobody downloaded it. And we were like, "Aw, shucks. This is terrible." And what we didn't really understand, which we
learned through this experience, was this. It's a Chris Dixon blog post which was Come for the tool, stay for the
network idea, which is that the first users of your product have to have some core utility that makes it useful for them
even when no one else in the world has the product, and with Flock, it was I download Flock, and it says great. Go
convince your friends to download this app so that you can get some value out of it, and 99% of people were like, "Cool.
Home screen," and they never used it again. That was the key insight there, and what we learned was that if wanted to
solve this automated photo-sharing problem, we had to upstream ourselves and get one step higher in the stack and
actually be the cameral roll. And if we were the camera roll, then everybody's going to be using the product anyway, and
then all this sharing stuff would actually work. And so that led us to the third product that we built.

Craig Cannon \[18:04\] - What gave you that insight, though, that you needed to go upstream?

David Lieb \[18:08\] - Basically, none of our friends were using it, and we're like--

Craig Cannon \[18:10\] - So just user conversations?

David Lieb \[18:12\] - Yeah, I would talk to a lot of the YC network. I'd go talk to them. I'm like, "Hey, I see that. I
looked in our logs. I see that you downloaded the app, but you're not using it. How come?" And people would say, and you
have to interpret what they say, but they would say, "Oh, none of my friends have it yet, so once they get it, then it's
going to be awesome."

Craig Cannon \[18:27\] - Gotcha, yeah.

David Lieb \[18:28\] - And that led us to see, okay, but you're not driving your friend to get it, whereas in Bump, you
were driving your friend to get it. What's the difference? And the difference was this novelty factor of it's this cool
thing that you want to show off. For Flock, the world had moved a little bit. There were a lot of photo-sharing apps.
People felt this burden to convince their friend, "Hey, I want you to download another photo-sharing app. It'll be
really cool."

Gustaf Alströmer \[18:50\] - And there's something about the physical virality, the physical bumpingness-- That people
see. There are some they use that are like Pokemon Go. You run around the street holding up your phone. People are going
to take notice, but that's not really the case with most apps. You just look at phone, and now I have no idea what
you're doing.

David Lieb \[19:04\] - Exactly. The physical nature of Bump, I think, made a big difference. I remember the first time I
saw someone in the wild bump that wasn't my friend, and it was a really visceral feeling. I'm like, "Whoa, they just
used Bump. Crazy," so I think that was a big part of it as well.

Gustaf Alströmer \[19:20\] - Well, and this was kind of a magical time, a critical time for photo sharing. 2012,
Instagram was a year in. Could you anticipate at the time where photo sharing was going to go? It's very easy in
hindsight to always say, "Oh yeah, of course I knew photo sharing was going to be a billion, $2 billion thing."

David Lieb \[19:39\] - I like to think that we intellectually understood it, but I don't think we did. I think we more
emotionally understood it or personally understood it, and I think we really use this technique that PG talks about,
which is if you want to come up with great startup ideas, just try to live at the edge of the future. Be the power user
of whatever thing you're interested in, and then things will just be obvious to you, and you won't even intellectually
understand them. You'll just be like, "This is useful and cool. I'm going to go build it." And I think that's what
happened to us. We were, in hindsight, looking back, it's now obviously to me, but growing up, I was always the person
in my family that would organize the photos and make sure the photos were taken. I was the person who would always ask
my parents, "Hey, can we do a slideshow night, and you tell me who these people in these photos were?" So looking
backwards, it's obviously that I was interested in this space, but at the time, we were all using iPhones a lot, and we
were taking a bunch of photos. We were seeing these problems of, oh, my iPhone is almost full. I better offload it to my
Mac, and we were doing the cable connection, but normal people were just like, "yeah, my phone's getting full. I'm going
to delete some photos," and we were like, "Oh, that's unfortunate. You shouldn't have to do that." And I think that kind
of led us from Flock. It made us realize there was this whole other set of problems when it comes to photos that nobody
was really solving yet,

David Lieb \[20:56\] - and we were personally experience them, and so that combined with the failure of Flock and the
success of it for people who did get it made us realize we should build this third product. So the third product we
built was this produce we called Photo Roll. It was really like a better photo gallery app. This was right on the heels
of when Inbox launched. I don't know if people remember this, but it was a better email client, and so we were going to
try to pull an Inbox and build a better photo product and just distribute it on the app store, and people could
download, replace their default app with it, and we built a prototype of it. I was using it on my phone, and it was
really great, and it had Flock built into it on the side, and so that made it so that people could just download this
better photo gallery app, and then all of a sudden as their friends started to get it, it just started to light up for
this photo-sharing behavior. Unfortunately, we had this great insight kind of at the end of our runway from our $20
million that we had raised, and we realized, "Okay, this photo product is a winner if we can figure out a way to have a
long runway and build it," but "Ooh, we're going to have to go raise a Series C on Bump to try to do it, and we're not
even raising that money to go work on this 150 million-user product that we've got," and it was just a very. We looked
at it, and we said, "I wouldn't invest in that."

Gustaf Alströmer \[22:12\] - Got it. Let's talk about fundraising a little bit, because we haven't even mentioned that
at all. After you guys raised from some of the absolute top VCs in the world. Talk about how that went and sort of how
it feels from the outside. From the inside, I would say around things like why you must be the most successful company
ever out of YC. How does that feel?

David Lieb \[22:29\] - We were very fortunate. We raised from Sequoia for our Series A. Our bridge round before that was
Ron Conway, and then our Series B was Marc Andreessen at Andreessen Horowitz, so we has the cream of the crop in terms
of investors. It felt really great, and we ignorant to the truths of the world about were we actually going to be a
really successful company or not. We didn't know, and honestly, I don't think any of the investors knew at the
beginning. What we saw was mobile is this huge wave that we all knew was going to be really big, and Bump was the most
popular app on mobile, and it solved some of these core problems that we all believed would be real. That was the
investment thesis. That was our kind of investment thesis for dropping out of business school and doing this is it's
working. Mobile's going to be big. We got to give it a shot, and I think that was the same way that we looked at it.

Gustaf Alströmer \[23:19\] - How was the fundraising experience like?

David Lieb \[23:21\] - It was very easy. I feel guilty saying it, but it was super easy. In YC, I think we got to, I
think it was either four or eight million users during YC, which at the time was just unheard of, so everybody wanted to
invest, and we met Sequoia folks, and we thought, "Oh, they're pretty good. We'll take them." And then, we raised that
round, and then I think it was six months later. Marc emailed me, and he's like, "Hey, I want to invest." I'm like,
"Marc, I just raised my Series A. I've got $2 million left. What are you talking about?" And he said, "I think it's
going to be big. I want to invest." And so we took the meeting, and I think we delayed it another six months, but then
we raised $17 million from them. It was, again, on this thesis that we don't know where this is going to go, but it's
going to go somewhere very interesting, so let's just plow ahead. In hindsight, I wish I had raised a little bit less
money in that Series B, because it would have forced us to have some of these existential questions or discussions a
little bit earlier. Because we had so much runway, we could just say, "Well, we'll figure it out," and we just kind of
kept for maybe an extra year in there.

Gustaf Alströmer \[24:25\] - That question comes up with founders a lot that I am talking to, so if they're doing really
well at fundraising, and they're like, well, there's more investors that want to give me another $3 million now. Should
I take it with that extra dilution? And my advice is typically, "Well, if you have discipline and you can put half of
the money in a different bank account and don't touch it for 12 or 18 months, then you should take it," but most people
actually don't have the discipline.

David Lieb \[24:45\] - It's true and investors want you to use the money. No investor wants to say, oh yeah, I've moved
some capital from my LP account into a different bank account, but it's just going to sit there. Don't worry. It's
earning 1% interest. Nobody wants to hear that, so it's very difficult to do that. What I would, the advice I give
entrepreneurs is raise more money if you know how you're going to use that money today. If you have no idea how you're
going to raise it, you're just like, I need some more money, you should only do that if you already have a very proven
business model, and there's risks that you want to mitigate. I'm an investor in Flexport. They just raised a big round,
and I doubt he knows exactly how he's going to use that money today, but he knows I've got a thing that's working.
There's existential risks that I want to mitigate, and so you raise that round. But at the early stage, I'm very
skeptical of raising money when you don't know why you need it.

Craig Cannon \[25:34\] - In retrospect, do you think you could have pulled it out of the tailspin and turned a
profitable product out of all the work you put in?

David Lieb \[25:41\] - Oh, I think we totally could've made Bump profitable. I just didn't think--

Craig Cannon \[25:45\] - But not at the scale.

David Lieb \[25:46\] - I don't think we could've made it profitable at the scale that a Sequoia or an Andreessen
Horowitz needs it to be. So had we not raised VC funding, I think it would've been a great business. We would've made a
freemium model where 1% of users bought the app for a dollar or something like that, and it would've been great.

Craig Cannon \[26:02\] - Right, but then it's also tricky going in thinking about raising a Series C for a product that
also might not be profitable at all.

David Lieb \[26:07\] - We looked at Photo Roll, and we were like, "People are going to love this. It's going to be big.
If we could get it to be distributed or part of an operating system like either Apple or Google, we think it would be
pretty good." But then, we were like, "And that would cost a lot of money if we were going to do it," because we wanted
to store all the photos in the cloud, and so we did the math, and we were like, "Okay, storing all the photos of the
world is going to be expensive in the future." And so we kind of decided to do this right, you've got to do it in a big
environment where you can have very longterm horizons, and so when we were getting acquired, we had a number of options,
and with Google, it really just clicked in terms of how we would fit into the mission of the company. The mission of
Google is to organize the world's information, make it universally acceptable and useful, and for photos now, Google
Photos, our mission was store all your photos, be a home for your photos, make them as useful as possible to you, and
then get them to the people that want them, which is exactly mirroring the Google mission, so that felt really good. The
DNA or the cultures of the companies were very much aligned. At Bump, we kind of like nerdy, quirky people, and we were
into physics and into math and that sort of thing, and at Google, we felt at home. Compared to when we would talk to
Facebook or talk to Apple, the DNA fit just wasn't quite as good, I think, so that was another reason that Google was a
good--

Gustaf Alströmer \[27:34\] - Was their lead on the Android team? Was there a photos team that you joined? There was a
photos app, Picasa back in the days, right?

David Lieb \[27:39\] - Google has been on the photos trajectory for a while, beginning with Picasa. There was an
acquisition. I think it was in 2005 to acquire Picasa, and then Picasa turned into Picasa Web, and then when Google+
launched, it got rolled into Google+, and so we showed up in the fall of 2013, and Google was full speed ahead on
Google+, and they were starting to build more and more photo-related features into Google+ with the goal of getting you
to share them on the social network. Our conversation with Google began with the Android team, and it was in the context
of the Gallery app on Android could be a lot better and smarter, and here's an app that could do it, and so the
acquisition was really to take Photo Roll and turn it into something that would be useful at the Google scale. And it
was really convenient. We joined Google, and we started to ask around about who's working on what, and we actually were
now moved over as part of this photos team inside of Google+. And I showed up, and I'm like, "Hey, I've got this idea
that I think is going to work around building a photo gallery app, a private photo-management tool that allowed you to
share and had this cool AI stuff in it," and I was kind of like, "But I don't have an AI." We're just posers here. And
we showed up, and we looked around, and we were like, "Oh, wow." They've got this huge team working on face recognition,
face-grouping technology. They've got this other huge team working on understanding the content of images

David Lieb \[28:58\] - and being able to search images. They've got this other team around scalably backing up photos at
a huge scale. And I just saw all this, and I'm like, "Oh, this is going to be good."

Gustaf Alströmer \[29:10\] - It was a great fit.

David Lieb \[29:10\] - It was a perfect fit. What I think we brought to the table as Photo Roll was this insight around
how do people think about their photos. What is the right design of a product? How do you build these sorts of features
in a way that would fit into their lives really well? And so the combination of those two things turned into Google
Photos, and--

Gustaf Alströmer \[29:31\] - And that mission of actually uploading every single photo for every single album is
actually there right now. That's what you do.

David Lieb \[29:36\] - Yeah, we do. We upload a lot of photos every day.

Craig Cannon \[29:39\] - What was the insight that led you to create? I understand the sharing between people, the
facial recognition. That's awesome. Searching is so cool. What was the insight that led you to start doing the
animations and stuff like that?

David Lieb \[29:51\] - A lot of that stuff was actually already being done inside of Google+, and they did it to try to
give you something interesting that would be post worthy, that would make you want to post it on G+. The process that we
took when we were designing Google Photos was to use this technique that I like to use a lot, which is pretend that
there's a human being doing the thing that your product is going to do, and pretend that human being doesn't have to
sleep, is really smart, has access to all the computing power and brain power in the world. What could that human being
do for you? We were talking about this earlier this morning, but for photos, I thought, "Okay, if my co-founder, Andy,
was my photo assistant, and all he did all day long was help me with my photos, what would he do?" And we just started
brainstorming. What were the things he would do that would be useful to me? Things were like make sure that he backed up
a copy of every photo, so if I lost my phone, I didn't lose my photos. Cool. He would look at all the photos, and he
would know who's important to me in my life. He'd know who's my mom, who's my dad, who's my sister, who's my girlfriend.
He'd write on the back of each of those photos metaphorically. This one contains mom and dad. This one contains Jenna.
And then we were like, "Well, what else could he do?" And then, I'd say, "Oh, I'd kind of ask him to go learn Final Cut
Pro," and I'd want him to make me cool montage movies of my life when there's something interesting. I'd want him to
remind me

David Lieb \[31:12\] - when it's the one-year anniversary of something cool that happened in my life or something
meaningful. I'd want him to go edit my photos. If I have a photo that's too dark or messed up, I'd want him to edit it.
If I have photos that are blurry or crappy, I'd want him to suggest that I get rid of those. We just made this laundry
list of things that would actually be really useful to me but no one was doing because we didn't have that Andy doing it
for me, and that was the insight that kind of led us to how we designed Google Photos, which was it's your home for your
photos, but then it's basically like this really helpful assistant that would just do all this other stuff for you. That
persists to this day, and it's working very well, that model.

Gustaf Alströmer \[31:52\] - What's your day to day look like today when you come into work at Google? How's it like to
run one of the 17 billion-user apps in the world?

David Lieb \[32:02\] - It's great. It's very diverse. How I spend my time is very diverse, I would say. I'll answer it
on a monthly basis rather than a daily basis, just because every day is very different. On a monthly basis, I think I
spend a quarter of my time, maybe, thinking about the strategy aspects like where should we take the team, where should
we take the product. What is changing about the world or our user base that we need to understand and kind of move in
one direction or another? Maybe another quarter is working with our team and helping our team, whether that be
developing managers on our team, figuring out how to structure the team, which leaders should we put in charge of which
things. That's another quarter. Another quarter, which is probably my most pleasurable quarter, is actually working with
people on our team directly to think about what we should do with the product, thinking about okay, what should we
change for our sharing model? How can we make it better? Or one that I'm working on right now is this photo assistant
capability that we have. What's the next step? How do we do something more with that? That's another quarter. And then,
the last quarter is stuff that you've got to do if you're running a team, and it's help people with feedback. How do
they get better as a team? How do they get better as an individual? Kind of the stuff that you don't think about when
you're a startup with 10 people, but when you're a company with hundreds of people, you're like, "Okay, I need to come
up with a good system where we can give feedback to people on our team.

David Lieb \[33:29\] - We can help develop them. We can make them better."

Craig Cannon \[33:31\] - This was the next thing I wanted to talk to you about. How do you think about your work now?
Coming from basically three people to a small startup to now a very big team, obviously the management strategies are
different. How you spend your time is different, but how do you actually feel about it? It's very different.

David Lieb \[33:50\] - Yeah, people ask me this question all the time. They're like, "What was it like? What was the
culture shock like going from a startup to a big company?" And I think I might be lucky, but it doesn't feel like that
at all to me. It feels like our startup acquired a multi-hundred-person team at a big company. It really does, and I
think it just says, it speaks volumes to the fact that our DNA match with Google was really good and that when we
joined, we eventually were given the autonomy and authority to actually chart the path for this product, and that was a
rocky road, but eventually we got there. That's how it feels to me, and it's really, it's a luxury. It feels great.
After kind of having that insight at Google, when I invest in companies, this is a question I explicitly ask them is if
you could go acquire a big company with the purpose of furthering your vision, which big company would you acquire? And
hearing the answer to that question helps me understand, A, their ambition and, B, how do they think about where they
want to take this thing long term. And so I often ask this question, and they're like, Wait, we don't have any money. We
can't acquire a company. What are you talking about? I'm like, "No, no. It's a thought experiment. Just tell me," and I
think it's really fascinating to hear those answers.

Gustaf Alströmer \[35:03\] - One thing I'm curious about. I would argue that Google Photos is one of the magical AI
experiences where you actually take a great product and you add machine learning and AI and make it magical, and there
are lots of startups that come to YC and apply with ideas that relates to AI, but how do you think about, what would you
advise them to say I have this product, and I have this machine learning capability that I'm adding to it? What do you
typically, when you see those companies, what do you ask them, and what do you advise them?

David Lieb \[35:33\] - The thing that really worked about Google Photos is it was one of the first examples of AI
solving real problems that people could resonate with. A lot of the AI stuff I see does not do that, and you're like,
how does the AI actually uniquely make this better, so in thinking about how you could apply AI, I kind of think about
it in two different vectors. One vector is is there a thing that human beings can do, either with skill or time or
resources, that they don't do at scale today, but we could bring a computer in to do that job? That's kind of what
Google Photos, that's our approach in many ways, and I think there's a lot of problems that could be solved in the world
that today you could solve easily with a good human being, but you just don't have that many good human beings at the
right price to do that, right? So that's one vector that I love to see, and that one I fully believe in. The other
vector is problems that human beings cannot solve today, things like how do you optimizing the power usage of a data
center? A human being could never solve that problem. It's way too, it's beyond our brains. That's the other vector
where AI can do really fascinating things, and I think that one is a lot harder to know a priori whether it's going to
work or not, and so those ones are riskier bets, but in many cases, they're much bigger payoffs if you can get it right.
So that's how I think about it. So my advice to people who are an AI startup is tell me which of those two are you. Are
you trying to solve this unsolvable human problem,

David Lieb \[37:00\] - or are you just trying to scale a very solvable human problem to a whole lot of people or at a
much cheaper price. And when you're doing that, what are the thing's you're going to go build? What is the solution that
you're going to try to show to your users? And if your answer is something that the solution, even though the AI tech is
super cool, if the solution is like, yeah, that's nice, but whatever, then it's not going to work.

Craig Cannon \[37:20\] - And so it seems like this attention to the user and attention to product is a core belief of
yours. It's not about the technology.

David Lieb \[37:27\] - Absolutely, and this was a thing that I noticed at Google when I joined, and I think since that
period, in the five years that have passed, Google has really made a transformation to focus much more on the user. But
at the time, there was still a lot of cool tech being developed, and everybody at Google is a technologist, and they're
like, "Oh yeah, this is really cool," but they weren't asking the question as much about, well, how does it solve a user
problem, and is it really a core user problem that we should solve? And so I think as Sundar has taken over at Google,
he's really tried to focus the company on the user and how can we be helpful to users, and I think that has just really
played out in the form of Google Photos.

Gustaf Alströmer \[38:04\] - Is it different to talking to users at scale when you-

David Lieb \[38:07\] - Oh, yeah.

Gustaf Alströmer \[38:08\] - Run a billion-user app versus when you were in a startup? How is that different?

David Lieb \[38:11\] - Yeah, I've got a tab open in my Chrome browser for each of our platforms, for iOS, Android, and
web, that is the raw stream of feedback that you can send in the app, and every day, we get thousands of reports. I
can't even read them all anymore, whereas at the startup, I could read every single email. In fact, at Bump, until I
think through the acquisition, I was the only customer support person. I wrote back to every single email, and I blocked
an hour or an hour and a half every day doing it, and it was kind of one of these things that can't scale and it was
probably a bad use of my time at some point, but it taught me that you listen to people, and generally, they will tell
you what you should do. You just need to understand how to interpret what they're saying.

Gustaf Alströmer \[38:51\] - It's a great practice. I think it's something we should recommend all early startups to do,
because it gives you just the right connection with the users.

David Lieb \[38:57\] - Yeah, one thing we did at Bump, which I really enjoyed, is we would take our team and go to bars
and do user testing and talk to people. One reason we did it at bars is that people are in a more social environment, so
bumping was something that you would actually do there, whereas managing your photos maybe is harder to find the moment
when people are in that mode. But the other thing is when people have a couple drinks, they actually tell you what they
think, whereas when you bring someone into a lab and set them down behind the mirrored glass, they know they're being
studied, and so they behave differently. This is a thing that I think is challenging at scale is how do you do that? You
can't just tell Google employees, "Yeah, go to bars and ask people what they think." It's not going to work. I would say
it's an area that, in general, could probably be improved, is how do you create these learnings and this empathy with
users at scale for a team that's large and for a user base that's very large.

Craig Cannon \[39:49\] - Do you have a system that's just parsing their text and looking for keywords?

David Lieb \[39:53\] - We do, yeah. We have some AI systems that read the feedback, try to cluster it into different
clusters, and then some humans look at that and try to understand if there's interesting insights. We've got a user
research team that goes out into the world and asks people. We do trips. A couple summers ago, I spent two weeks in
India just living in India, trying to understand what about Indian people is different than what is about people in
Mountain View, and there's a lot of differences. We try to do stuff like that. We bring people into our office also, but
again, that has its own challenges in terms of knowing that you're being tested. We try to do as much of this as
possible, and I honestly, I put a lot of weight into what intuition you can build by just talking to your users. I think
we overlook the fact that we've got the best computing platform that has ever been built, and it's our brains, and we
can use it to give it inputs, and then let it do its magic and pattern match, and then output our intuition. And I think
that is really what your gut is, and it really is like a sophisticated machine learning system that we should actually
utilize, so I'm a big believer in building what you think is right.

Craig Cannon \[40:59\] - Absolutely. A question from Twitter related to products. Lamide Akkamolafe, hopefully I got
that right, asks, "What did David focus on too much that he thinks was a mistake now when you were a rookie product
lead?"

David Lieb \[41:14\] - Oh, great question. What did we focus on too much? One thing at Bump that we've focused on a lot
was how good the system was, how performant was it. We obsessed over microseconds here and milliseconds there, and I
love that culture, and it's a culture that we try to really push on Google Photos as well, but I think if you focus on
that a little too much early on, you might be missing the much bigger picture, which is even if you made it super
awesome, people aren't going to care. And I think that is an insight that is hard to really have when you're in the
moment, in the details, your system is running, and you're like, crap. It's really slow right now. All the users are
complaining. It's so easy just to be like, great, let's go fix that, and it's very hard to pull back and say maybe
that's not the problem we should be fixing. Maybe there's some other problem that we need to understand. And I think
that is the trap that a lot of companies fall into. This is the Sam Altman. It's one of my favorite quotes from Sam is,
I think it's like he says, "The meta problem that kills most startups is working on the wrong thing." It's not screwing
up whatever you're working on. It's not your competitors. It's that you were just focused on the wrong thing, and I
think that in the product world, it's this trap that you can fall in which is like, "Oh, this is not as good as it could
be. We should make it better," where even if you made it perfect, it doesn't matter, and actually, you needed to work on
this other thing. So that's probably my number one advice.

Craig Cannon \[42:42\] - Now that you're working on it at large scale, these product insights, what degree of buy in do
you have to feel before you ship it out to a billion people when you're testing some new thing?

David Lieb \[42:54\] - Great question. We do a number of things to get confidence in some product that we're going to
build or some feature that we're going to build. The first thing we do is use it ourselves, and if we think it's not
working, then it's very likely it's not going to work in the market. This is a luxury that we have because we build
Google Photos. It's a product that we're building for ourselves and for a lot of other people who are not like us, but
we are at least somewhat representative of the user base, compared to if we were building a product for kids that are
under eight years old. I personally don't have a ton of intuition about that, and I wouldn't be able to know innately
whether this is going to work or not, so that's a whole lot more challenging problem, and I have so much respect for
people who can solve problems where they are not the user. For us, we are the user, so the first step is do we like it.
And often, I challenge our team, where we've done experiments. We've run stuff. We were about to launch something, and I
just ask the team. I'm like, "What do you guys think about it? Do you like it? Do you use it? What's your most annoying
part of the product?" And often, they're like, "Well, I'm not the target user, but this is kind of annoying to me." And
I'm like, "We should get that right. Come on." So that's number one. Number two is we do a bunch of testing with users
before we actually launch. Even in an experiment, we make prototypes. We bring them out to people,

David Lieb \[44:14\] - and you can learn a lot of usability things, like whether the actual flows will work, but you
can't really test do they care by doing those sorts of tests. We also do experiments. We roll things out to 1%. We've
got a, I won't talk about it, but we've got a pretty big product in experiment right now that we're excited about, and
we're watching how people are using it. We're trying to keep it on the down low. And that's another thing that we do,
and we learned a lot from that. and I think the combination of all these things gives us confidence that yep, this is
the thing that we at least have high enough confidence that we should roll it out and see what happens.

Gustaf Alströmer \[44:47\] - Lamida Akumolafa is asking you, "Did you make any early mistakes when you joined Google?"
So as product lead, what kind of... This is new, large organizations to you. What kind of mistakes were you doing?

David Lieb \[45:00\] - My bosses would certainly say yes. Let's see, there are two problems and they're wrapped
together. The meta problem that I made, or meta mistake I made was I really believed in this vision for what we could
build in the photo space so much that I was just determined to solve it. And I think the skill that I needed to develop
inside of a big company, which is very different than what I had at the startup was, I now had like three or four bosses
above me that I needed to convince. And at the startup, I just had to have a board meeting and say, "Hey, Marc, I'm
going to do this." And he's like, "Cool, do it," whereas here, it was, like, "Hey, I got to convince this person. And
then I've got to use their support to garner support from this other group of people. And then I've got to take that and
create support from the CEO," right? And it's a very different process. And I was not very adept at doing that. And I
just kind of, I use the modality of being the startup founder, and just saying, "We need to do this. Come on, everybody.
Let's go, and I'm going to convince you." And whereas at Google, I needed to be much more delicate. And I don't think I
did a great job of that. One of the subcomponents of that was how can you do that at a big company? And I have learned
now is you can really get a lot of support at the grassroots level. So when I ran into these problems going up the stack
at Google, I kind of retrenched and said, "Great, let me go talk to the people on the ground actually talking to
customers actually building the product,

David Lieb \[46:29\] - "as opposed to the people managing big teams doing it." And when I would go talk to those people,
a lot of them said, "Oh, yeah, I get it. Let's do it. This makes a lot of sense." And by building some support there, we
could then go in mass to the the leader and say, "Hey, we all think it's right. Here's all the perspectives. Here's all
the diverse opinions. This is what we think we should do," and that is a much better sell at a company, especially if
you can have evidence in the market in some way that like this stuff is working. This other stuff is not working. Let's
look at it objectively and decide what we should do.

Craig Cannon \[47:02\] - In five or 10 years, do you see yourself working for a large company or startup?

David Lieb \[47:05\] - That's a great question. I love startups. I love the the rawness of startups, the purity. They're
like every problem you face is like there's no layers of abstraction. You're just in it, and you're seeing the true
problem. I love that. It's a thing I try to keep doing at Google. The challenge is was when I look at what I could go
start next or whether I want to join a startup or start a new startup. I kind of have the luxury of thinking about it in
two dimensions. One is, what reach will I have? How many people in the world can I affect with this thing I want to
build? And the other dimension is to what degree can I affect their lives in a positive way? And looking at Google
Photos, it's like we have a path to affect billions of users, the majority of people on the planet. We have a path to
get there. That's pretty amazing. Not many products can do that. And then on the importance or depth of the experience,
I believe there's not a lot of things more valuable to you, than the record of your life, your memories, right? Maybe
the only things on top of that are being alive, your health, and maybe connections in the moment to the people around
you. Otherwise, it's one of the most essential parts of the human experience. So I look at that, and I'm like, "I think
this is probably the most impactful thing I can be doing right now."

Gustaf Alströmer \[48:23\] - I actually give that advice. When companies ask me, "Hey, I got this acquisition offer from
this large company," I always try to put all the financial stuff aside and so everything else, and the main question to
me is always, can you execute your vision towards a much larger audience in a better way inside this company or not? And
if you really believe that being part of this other large company is the way for you to get to your users and see your
vision, then that is the most important question to answer.

David Lieb \[48:47\] - A corollary is if you don't have that alignment, and you do go to that company, it's going to be
a disaster.

Gustaf Alströmer \[48:56\] - Statistically, most acquisitions don't turn out well.

David Lieb \[48:58\] - Yeah, and it's fascinating. You make this big decision for your company that we're going to go
get acquired by blank. But then, if you look at how many minutes or hours did I spend with the people I will be spending
my entire work life with, it's usually really, really small, laughably small.

Gustaf Alströmer \[49:15\] - And most of the discussions is on the financial outcome.

David Lieb \[49:17\] - Yeah, exactly.

Gustaf Alströmer \[49:17\] - It's not actually about sort of like the product outcome. That should be where--

David Lieb \[49:21\] - Exactly, so a lot of the challenges I faced when I got to Google were misalignments of vision
around what Google should do in the photo space. And I wish we had had those conversations beforehand. The problem is
the conversations need to be with these senior-level people at Google, and they don't have time to spend an entire
weekend spit balling with me about some some random startup entrepreneur. The future of what we should do--

Gustaf Alströmer \[49:43\] - It might or might not get acquired

David Lieb \[49:45\] - Exactly, it's this asymmetric problem. And now that I'm on the other side at Google, I try to
empathize with my former self. And we've done acquisitions at photos, and I try to just spend a lot of time with people,
make sure that we're aligned on what we want to build, because inevitably, when you join, something's going to change,
and you're going to have to tweak your plan in some way. And if you don't have that fundamental alignment, it's going to
be a disaster, so that's the other thing I think is really important.

Craig Cannon \[50:13\] - You said something really interesting about humans and their attachment to photos. I wanted to
kind of touch on this at some point. Have you learned any kind of larger truths about humanity by paying attention to
all of this stuff all the time for years?

David Lieb \[50:27\] - Probably, I don't know if I'm great at articulating them. Let's see. Probably the number one
truth I've seen is the power of nostalgia. I think we all feel it, and we all know that feeling, but seeing it from the
perspective that I get to see it, it's one of the most powerful things in the human experience, I think. And we've
tapped into it in a variety of little ways, but I think there's a much larger thing that we're still trying to go learn
and figure out. We each think about important moments in our lives, and they can be important from a grandiose
perspective or just little moments in our lives that stick with us. And usually, in that moment, there's an image that
you have in your brain, or a song that you associate with that moment, or a smell. There's something that triggers you,
and people love thinking about the past. It's just an innate thing, and I think it's an evolutionary thing that those of
us who had that trait are better at understanding where we've been and better at surviving in the future, so I think it
is baked into us as humans. But it is a really powerful phenomenon.

Gustaf Alströmer \[51:38\] - Have you read Thinking Fast and Slow-- Whre he talks about sort of how important
photographic memories are for happiness?

David Lieb \[51:43\] - Yeah, I have, and I totally believe it. One of our goals with Google Photos is to basically give
everyone a photographic memory. The challenge is our brains aren't. Most of us, at least don't have this perfectly
linear, evenly distributed, photographic memory. The way our brains work is we pick important moments and really, like
write a lot to the disk during those moments, and then we kind of don't worry about the rest. One of the challenges we
have with Google Photos is we now have all the photos that you've taken in your life. How do we decide which ones are
the important ones that we should really focus on and try to help you relive and engage with? Which ones are not
important, even though they may seem important to our algorithms\> And then, on the other side, which ones are not
memories that you want to re engage with? And this is a big challenge, and it's a very difficult problem, but we all
have moments in our lives or people in our lives that were part of our life before. And it was an experience we had, but
going forward, it's not a thing that we want to dwell on, and that's a really difficult challenge. I would say, we're
getting it okay, but not great, and that's an area want to improve.

Gustaf Alströmer \[52:46\] - I have one final question. As a product lead, I had a similar role at Airbnb. I spent a lot
of time looking at other products and new products. What are your top other new apps that you are pretty excited about?

David Lieb \[52:58\] - In the photo space?

Gustaf Alströmer \[52:58\] - Or even in general, In general. Apps that just you feel now, these are important to me.

David Lieb \[53:03\] - Yeah, oh, consumer products.

Gustaf Alströmer \[53:05\] - Yeah, or just apps generally.

David Lieb \[53:06\] - Yeah, well, in terms of categories that I see that I'm interested in, spanning everything, one
category that I think is fascinating is basically taking mundane systems that humans have created and replacing them
with smart technology. Flexport is one example of that. I just invested last YC batch in this company, Canary
Technologies, building software for hotels. Seems so mundane, and who cares about that, but it's a big problem. A lot of
people go to hotels, and we need to make the experiences better, and one way to do it is to make the software better.
That's one category that I'm very interested in. Another category that I'm interested in is taking things that we all
take for granted, like eating food or having health care, and applying some of these technologies or things to make
those things better. One I just invested in also in the last batch is Seattle Food Tech. They're making a meatless
chicken nugget. I just ate them the other day, the newest version of it, and they're delicious. And it's like obvious to
me that, "Oh, yeah, we're going to, this will be a thing." Some form of this will be a thing, so applying technology to
these very mundane, physical parts of our lives is another category that's interesting. On the consumer, social, yada,
yada side, it's really tough. I see lots of cool stuff where I'm like, "There's something cool in there, but this
thing's going to fail." And I think that all the time, and I tried to invest in them, because some fraction of them will
become really cool.

Gustaf Alströmer \[54:32\] - It's a different world today than we were--

David Lieb \[54:35\] - Oh, it definitely is.

Gustaf Alströmer \[54:35\] - five, seven years ago.

David Lieb \[54:36\] - Developers have gone and figured out all the obvious wins already in the consumer space, and the
ones that emerge are the ones that seem totally off the cut. Who would've known 10 years ago that Snapchat would have
been like a popular thing or that the stories format would have been a popular thing? It's very hard to predict until
you build it and see it, and then you're like, "Oh, yeah, that's going to work."

Craig Cannon \[55:00\] - Well, let alone lip a syncing product becomes--

David Lieb \[55:02\] - Yeah, and I think one thing on the consumer side that I've come to understand is there is a
difference between something that is really popular for a while and something that is a durable, essential human need.
Through the Instagram phase, given where I am in Photos, I got to see all the Instagram competitors, where they have
some new cool format, right? It turns your photos into art, or it makes this part of the photo move, or it's this cool
looping effect. And all of them have the thesis, we're going to take this and turn it into Instagram, and my feedback
was always, "But Instagram already exists. So you're not solving a durable human need."

Gustaf Alströmer \[55:42\] - What was it the timing, or was it a specific thing that they did that made them succeed?

David Lieb \[55:46\] - I think had those things happened before Instagram happened, they could have pulled the same
thing off. Instagram pulled the same playbook, right? It's, "Yeah, we let you filter your photos. They look slightly
different," but then they were able to translate that into a network that was durable and a human need that was durable,
which is I want to interact with other people, basically. That's basically what Instagram is. And so when I look at
consumer stuff, I try to understand what is the fundamental human need that your product is either scaling across time
and space or changing or amping up in some critical dimension? And if I don't see that, then I'm much more skeptical,
right? That's kind of my rubric for consumer stuff is tell me the thing that humans already do today in a limited, not
as great way that you are going to somehow amplify times 10 or times 100. That's what Facebook was. That's what Twitter
is. That's what Snapchat is. All these things are exactly that playbook executed really well.

Craig Cannon \[56:40\] - Right on. All right, thanks so much for coming in.

Gustaf Alströmer \[56:42\] - Thank you so much.

David Lieb \[56:42\] - All right, thanks Gus.

Gustaf Alströmer \[56:43\] - It was great.

