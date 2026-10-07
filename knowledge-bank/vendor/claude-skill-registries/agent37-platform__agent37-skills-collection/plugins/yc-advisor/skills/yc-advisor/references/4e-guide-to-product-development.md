# Guide to product development

**Author:** Michael Seibel
**Type:** Essay
**URL:** https://www.ycombinator.com/library/4e-guide-to-product-development


---

Before Justin.tv grew into Twitch and Socialcam we spent years with a broken understanding of how to build product. We
had meandering product meetings where we didn’t write down our decisions. We didn’t carefully spec new products so team
members often had slightly different ideas about what we were building. We always wanted to build fully formed products
instead of MVPs. And we rarely spec’d the analytics for new products so we often didn’t know how they were performing
post-launch.

Development cycles often ran months. We were sick of the new feature by the time we launched them so we didn’t iterate.
Our product roadmap was so long that team members weren’t excited to brainstorm new products because it was unclear if
they would ever be built. And most horribly, product decisions were made exclusively by the founders in a
non-transparent process. Things were a mess.

In this post I’m going to cover product development cycle fundamentals that I learned to help solve all of the problems
above. This will help you rapidly iterate, measure, test, and improve your product while fully engaging your team. This
is not that same as shipping an MVP. I’m assuming you’ve released an MVP and are figuring out what to do next, which is
where most startups spend most of their time.

**Define Your Development Cycle Length** Your development cycle should be dictated by your product. At Socialcam we were
building for iOS so we settled on a two week cycle, which allowed us to thoroughly test before releasing to the App
Store. If you’re doing a web app your cycle can be shorter, if it’s hardware it might be longer. The key is to structure
the cycle so that teammates stay excited and still feel like they can brainstorm new ideas.

**Determine Your Goal(s) and Identify the Product Lead** We ran one and only one team meeting. It was the product
meeting and it happened on the first day of the dev cycle. Sometimes this meeting would go for five hours (sorry).

Every product meeting was focused around one of three goals:

1.  Increasing content creation
2.  Increasing new users
3.  Increasing retention

Whichever goal we chose would be the focus of the meeting and, therefore, the next two weeks.

As the product person on the team my role was to protect and improve the dev cycle and moderate the product meetings to
ensure all team members felt comfortable contributing. Oftentimes just getting the opportunity to voice your idea and
having it written on the board - even if it isn’t built - massively increases buy-in of the process.

**Organized and Inclusive Brainstorm** While we were brainstorming, ideas would be written on the whiteboard in one of
the following categories: new features/feature iterations, maintenance, and A/B tests. Everyone was expected to
contribute. Debates or putting down other people’s ideas wasn’t permitted. This was the time when everyone felt free to
contribute without fear of judgement. The product lead is responsible for creating and maintaining that environment.

From there each brainstormed item would be graded by the engineer in the meeting as easy (several can be done in a day),
medium (half a day for one person), and hard (most of the dev cycle). No item could be so hard that it would last into
another cycle and if it was, we’d break it into smaller chunks. Usually this grading would be done item by item by the
engineer with the most experience in that specific area. iOS features were ranked by the iOS guy and so on and so forth.
This really helped non-technical people understand which of their ideas were easy to build and which were hard. With
this realization they often got better at thinking up easier and easier MVPs of their ideas. These easy ideas would then
get built and, if they worked, would be iterated upon.

**Building a Consensus** Once we’d written our ideas out we began to pick what we would work in through consensus. We
would start with the hard ideas–it was easy to form consensus because we knew we could only do one and because we knew
that we would start a new dev cycle in two weeks. Then medium and then easy. Developing that consensus wasn’t very hard
because everyone had the opportunity to suggest their own ideas and because there was a clear goal and objective
measurement of how long each idea would take to build. This process allowed you to grade the quality of your own idea
and didn’t allow personalities to bully their pet ideas through.

**Clear Spec and Clear Measurements of Success** Afterwards we would spec out each of the items on our list in detail
and assign each item to a team member (or multiple team members). We would also spec the stats we needed to track in
order to measure how effective the feature was. We would never release a feature without releasing the analytics for
that feature and understanding what specific measurable result we wanted to create. Finally, we separated out the need
to haves from the nice to haves on the list. If there wasn’t time, the nice to haves would not be built. After that was
done we would take a picture of the whiteboard and delete it. We didn’t have a product roadmap outside of these two
weeks and every product meeting we would start from scratch with the new goal, new analytics data from our last two
weeks, and also often new insights from in-person user testing, which we tried to do once a month.

**Working During the Development Cycle** For me, work after the first monday of the development cycle was a silent
affair. My job was to get all the business and operations tasks done. Then I’d dig through Mixpanel looking for
interesting product insights or potential bugs. Finally, I also ran monthly user testing sessions in our office. My
teammates - engineers and a designer - would work quietly and quickly knowing they had projects with limited scopes that
were well spec’d out. Finally, during the last three days of every development cycle we would all stop building and
test. We had a testing list in Excel that included manual tests for all of our basic functionality. Every cycle we added
tests for new features built in that cycle and we tested all items on our testing list twice. Everyone on the team
tested and we often had competitions for who could test the fastest and who found the most bugs. Testing sucks so it’s
important that the burden is shared.

**The Results** At the end of the day, Socialcam did not achieve our dream of being the “Instagram for Video”. In fact
what we should have built looks a lot closer to Snapchat. But this process did allow us to iterate extremely quickly. As
a result we were able to produce a laundry list of cool features very quickly: video filters, video borders, video
titles, video soundtracks, video feed optimizations, multiple visual redesigns, user profiles, recommended channels,
front back camera switching during a video, and much much more. It also allowed us to experiment with growth features
that produced 16 million downloads in about 3 months and over 100 million people watching video on our website during
the same period of time. Most importantly though, we did all of this work quickly, efficiently, without major arguments,
issues with founder commitment, or really any team problems at all. Sometimes I wonder what would have happened if
instead of selling the company we kept building for another year… But that’s another story.

*Thank you Jared, Geoff, and Craig for helping me with this post, Ammon and Guillaume my co-founders at Socialcam, and
Justin, Emmett, and Kyle for surviving all the pain from the good old days at Justin.tv.*

