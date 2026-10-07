# The hidden forces behind China's content king Toutiao

**Author:** Anu Hariharan
**Type:** Essay
**URL:** https://www.ycombinator.com/library/3x-the-hidden-forces-behind-china-s-content-king-toutiao


---

*Special contributions from [Luke Pryor](https://twitter.com/lukepryor) and [Brad
Lightcap](https://twitter.com/bradlightcap).*

*Disclosure: I’m a personal investor in Toutiao.*

-----

**Using Machine and Deep Learning to Create and Serve Content, China’s Toutiao Created a Product with Engagement Similar
to that of Social Networks - All without a Social Graph**

Toutiao, one of the flagship products of Bytedance\*, may be the largest app you’ve never heard of–it’s like every news
feed you read, YouTube, and TechMeme in one. Over 120M people in China use it each day. Yet what’s most interesting
about Toutiao isn’t that people consume such varied content all in one place… it’s *how* Toutiao serves it up. Without
any explicit user inputs, social graph, or product purchase history to rely on, Toutiao offers a personalized, high
quality-content feed for each user that is powered by machine and deep learning algorithms.

Going a step further than merely serving up content, Toutiao’s algorithms also create content: During the 2016 Olympics,
a Toutiao bot wrote original news coverage, publishing stories on major events more quickly than traditional media
outlets. The bot-written articles enjoyed read rates (\# of reads and \# of impressions) in line with those produced at
a slower speed and higher cost by human writers on average.

The average user spends more than *74 minutes* each day in Toutiao -- that’s more than the average user spends on
Facebook<sup id="footnoteid1"><a href="#footnote1">1</a></sup>, and more than twice what they spend on
Snapchat<sup id="footnoteid2"><a href="#footnote2">2</a></sup>. More than half that time is spent watching short-form
videos; this coupled with over 10 billion video views per day makes Toutiao the YouTube of China (along with, of course,
everything else it offers).

How did Toutiao do this? Especially without massive consumer platforms at scale like those orchestrated by Chinese
conglomerates Alibaba, Baidu, and Tencent? In this post I’ll explore how Toutiao got to 120M daily active users. Toutiao
doesn’t attribute its growth to any one factor, but rather to the interplay between many tactical and strategic
decisions it made starting at launch; specifically, five key advantages, all of which I have outlined below. And while
“super apps” aren’t as common in the U.S., I believe there are specific lessons in this case that can inspire others
in building their own products and platforms.

**But first, a bit of background**

Toutiao launched in 2012. The app uses machine and deep learning algorithms to source and surface content that users
will find most interesting. Toutiao’s underlying technology learns about readers through their usage – taps, swipes,
time spent on each article, time of the day the user reads, pauses, comments, interactions with the content and location
– but doesn’t require any explicit input from the user and is not built on their social graph. Today, each user is
measured across millions of dimensions and the result is a personalized, extensive, and high-quality content feed for
every user, each time they open the app.

<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-Blog-Post-Graphic_Minutes.png" alt="Toutiao Blog Post Graphic_Minutes" width="1312" height="1868" class="aligncenter size-full wp-image-1101027" />

<center>
  Sources: Snapchat - S-1 filing. Instagram - <a href="https://www.recode.net/2017/8/2/16081086/instagram-snapchat-stories-anniversary-time-spent">Recode</a>. Facebook - Q1 2016 earnings report.
</center>

-----

# The Five Hidden Forces Behind Toutiao

## 1: Mind the gap, seize the opportunity

While timing is everything for a startup, it takes deliberate effort to build an addictive app. Toutiao’s timing was
fortuitous, but its exploitation of this unique moment was deliberate. Toutiao launched as smartphone use was taking off
in China: mobile penetration increased from nearly nothing in 2010 to 65%
by 2014<sup id="footnoteid3"><a href="#footnote3">3</a></sup>. Moreover, many of the largest content providers had not
yet developed mobile apps or mobile-friendly sites, meaning that true mobile-optimized information and entertainment was
rare. By mid-2012, there were only six significant news apps on the Chinese Android platform. Four of them were direct
extensions of existing news portals with limited mobile optimization, and the other two were aggregators that relied
exclusively on slow and impersonal editor input to determine what stories to show. Further, the Chinese audience's
demand for content (both articles and videos) was underserved by Chinese social networks such as WeChat and Weibo.
WeChat launched as a messenger and to this day has a closed social network (i.e. sharing/moments are private to friends
only).

Toutiao stepped into this gap with an easy-to-use, personalized, informative, and addictive mobile-first app. From the
outset, Toutiao was extremely easy to start using – all it took was a download. There was no need to create an account
and password, to link it to social media (unless the user so desired), or to provide information on interests or
preferences. The app’s simple design also made it intuitive to use with no prior knowledge or tutorials. For any app,
driving initial engagement – moving from downloads to DAUs – is notoriously difficult. It’s typical to lose users at
every step of the process due to discouragement, confusion, or annoyance.

The name of the app Jinri Toutiao (meaning “today’s headlines” in Chinese) and the icon of the app were catchy for
users, resulting in excellent user growth. It was also the first time various news articles were aggregated in one
place. From the very early days, Toutiao tracked information about each user - their taps, swipes, time spent per
article and location to power the recommendation engine which we will discuss later in the post. One month after launch,
Toutiao became a personalized news aggregator for several of its users. The product, the only one of its kind and
delicately designed at that time, led to a rapid growth. They hit 1M DAUs only four months after launch. Toutiao gave
new internet users something to “do” when their mobile time was still up for grabs. Toutiao updated the app almost
weekly throughout its first year, as it consistently innovated, iterated, and improved its features and algorithms, and
this resulted in improved retention over time.

In the years that followed, competition for user share of attention on mobile would drastically increase – the number of
mobile apps available in China more than tripled in the three years from 2012
to 2015<sup id="footnoteid4"><a href="#footnote4">4</a></sup>. But Toutiao’s early lead meant that, by the time
competitors arrived, it already had an important and valuable foothold.

*The image below shows the personalized feed of two different users.*

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-2-1.png" alt="Toutiao 2-1" width="2397" height="1729" class="aligncenter size-full wp-image-1101016" />](https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-2-1.png)

## 2: A data network effect deliberately built across the entire system

You can have all the algorithms in the world, but without an addictive product there is no data, and without data, no
algorithm can make the system better. Matt Turck has written about the power of the data network
[here](http://mattturck.com/the-power-of-data-network-effects/). Simply put, the more users use your product, the more
data they contribute. The more data they contribute, the smarter your product becomes. The smarter your product is
(e.g., better personalization, recommendations), the better it serves your users and they are more likely to come back
often and contribute more data — thus creating a virtuous cycle.

By building an addictive product, Toutiao generates engagement data from their users. That data is fed into Toutiao’s
algorithms, which in turn further refines the products’ quality. Ultimately, the company plans to use this virtuous
cycle to optimize every stage of what they call the “content lifecycle”: Creation, Curation, Recommendation and
Interaction.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-3-1.jpg" alt="Toutiao 3-1" width="4000" height="2250" class="aligncenter size-full wp-image-1101018" />](https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-3-1.jpg)

**Creation**  
Ever since the invention of written language, content creation has been the exclusive domain of humans. Toutiao looks to
change that. It’s begun with Xiaomingbot, an artificial intelligence that has already published more than 8,000 stories
on the platform to-date. It debuted during the Olympics in 2016, where it published stories on major events more quickly
(approximately 2 seconds after the event ended) than traditional media outlets. Indeed, the bot-authored articles
enjoyed read rates (\# of reads and \# of impressions) in-line with those produced at a slower speed and higher cost by
human writers on average.

*Below is a screenshot of an article written by the Xiaomingbot describing the results of the tennis match between Andy
Murray and Juan Martin Del Potro during the 2016 Olympics.*

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-4.jpeg" alt="Toutiao 4" width="750" height="1334" class="aligncenter size-full wp-image-1101006" />](https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-4.jpeg)

To achieve this, Toutiao had to overcome a couple of significant technical challenges:

First, writing stories on Olympic game results required data, and Toutiao pulled it from three sources: \[a\] real time
score updates from the Olympics organization, \[b\] images from an image-gathering-company it had recently acquired to
find relevant visual media, and \[c\] monitoring live text commentary about the game. It also started with four sports —
Table Tennis, Tennis, Badminton and Women’s Soccer — that were easier to recap from a technical standpoint (Table
Tennis, Tennis and Badminton are “turn-based” games and the rules of the games are simpler vs. other sports. Unique
access to a high-quality data source for Women’s Soccer made that the fourth game covered.)

Second, Toutiao had to figure out how to combine data from these three sources to ensure an internally consistent and
relevant story. This was a much larger challenge than even accessing and interpreting the data in the first place. Any
selected image needed to be relevant to the results of the event, and also appropriate for the takeaways from the
commentary. This, in turn, required Toutiao’s AI team to integrate natural language processing capabilities with
contextual image recognition. They ended up with a combination of a grammar-based representation for generating story
templates, a ranking algorithm to select relevant sentences from live text commentary, and an image-text matching
algorithm to tie it all together. The system also employs convolutional neural networks to analyze content in candidate
images. By training on historical data, the model is able to pick the most relevant and visually appealing image for the
story. They also use sequence-to-sequence deep learning algorithms to summarize existing stories into daily highlights
and suggest better titles for articles.The system employs recurrent neural networks to compute vector representation for
sentences and these sentence vectors are further fed into a ranking model to pick concise summaries for each article.

The products of these efforts – 450 published stories with 500-1,000 words during the Rio Olympics – that were hugely
successful. They enjoyed read rates (\# of reads divided by \# of impressions) on par with those produced at a slower
speed and higher cost by human writers. Toutiao has extended this capability beyond sports to over 8,000 stories
to-date, and is working hard to close some of the remaining technical loopholes that make human writers recognizable.

**Curation**  
A major engagement driver for Toutiao in its early days was “soft news”– areas like celebrity gossip, pop culture and
lifestyle articles. This was no accident. Contrary to official news, which was distributed by well-known state-owned
news sources, soft content was distributed across the internet on a plethora of individual sites. In short, there was no
central place to access the content: users who were looking for it would have to invest meaningful time in visiting
different sites, and had no assurance they were getting the most interesting information. Toutiao changed that. In
owning, centralizing, and optimizing the distribution, it reduced the time a user needed to find content to nearly zero,
and it increased their confidence that they were reading the most interesting stories. This created real value for
users.

At its core, content curation is a two-sided problem: the curator must find content, in addition to serving it to its
users. The first requires visiting websites, identifying stories, and collecting relevant metadata. The second requires
continuously updating a central repository of stories, and creating as many personalized versions as possible. Both are
process-intensive tasks where algorithms have a distinct advantage over humans. Toutiao’s only meaningful competition in
this space when it launched were web portals where human editors handled this work, and Toutiao’s use of algorithms gave
it a major advantage over the manual competition.

The speed with which the system could do what took human editors much longer translated directly into value for
Toutiao’s users. Toutiao could gather more content more quickly and at a lower cost, creating a major advantage in a
business were customer value is directly tied to content quality, relevance and refresh rate. The use of algorithms also
meant that each user could have their own, interest based and continuously updated profile – something that no human
editor would ever have the time to do.

Toutiao also uses algorithms to identify and filter out low-quality content. A content distribution platform is only as
good as the content it distributes. The days of mass-distributed cookie-cutter content (e.g., newspapers, magazines) are
over. In Toutiao’s world, the distribution platform only serves what is interesting to its users. False reporting and
spam are major issues in the media industry. Toutiao’s underlying technology uses a text classification algorithm to
determine if an article is fake news, uses clickbait titles, or doesn’t meet Toutiao’s quality standards. Here, Toutiao
also leans on user moderators to flag fake articles and employs human moderators to arbitrate on disputed reporting.

**Recommendation**  
Content recommendation is the feature for which Toutiao is best-known, and to which it owes much of its success and
reputation. The use of machine and deep learning algorithms at this stage of the content lifecycle is what has sets
Toutiao apart from its peers, and is key to driving continued user growth and retention.

The question that the recommendation engine is trying to solve is simple: **what are the one hundred articles the
platform can recommend to each user that are most likely to result in continued engagement?** This is a question with
major consequences – the AI team has recognized that 100 headlines is a retention “threshold” (users that do not retain
long-term tend to drop off dramatically after seeing \~100 headlines, similar to Facebook’s “10 friends” rule). It is
also a question that humans are unsuited to answer: no human editor could ever regularly and quickly identify the
optimal set of headlines for every one of the app’s new users.

As simple as the question may be, the solution is complex. For every new user, Toutiao blends signals from three key
areas to create a feed that it hopes is engaging and will push users over the 100-headline threshold:

  - User profiles: are initially built based on the app’s understanding of the user’s demographics (their age, location,
    gender, and socio-economic status)
  - Content: to understand the content of articles, Toutiao turns to natural language processing to determine if the
    article is trending, whether it is long or short, and the timeliness of the article (some articles are evergreen
    while others have a very short half-life)
  - Context: pertain to location-related data (localities like geography, weather, local news, etc.)

The underlying algorithms must then identify the strongest statistical match between the user’s profile, its own content
profile, and context, and it must do this on a continual basis. This matching is meant to optimize the percent of
articles a user reads (clicks on) and the percent of articles that a user finishes (measured by the time spent on the
page). When a user first opens the app, the system uses the basic data in the profile for the matching: a user in
Silicon Valley, for example, may be more likely to click on articles about tech. The system also makes sure to show a
variety of articles to assess interest/disinterest– in doing so, can help users discover previously unknown content and
test their potential interests. Over time, as the app collects user information, these recommendations get further and
further refined. The engine learns quickly – for most users, it takes less than one day to successfully learn their
interests (indicated by 80% read rates). The result is the case of strong user retention (\>45%) that is similar to
social networks and one of the largest time spent per user apps in the world.

**Interaction**  
As Toutiao has grown, interaction on the platform has become more and more central to its user value proposition. Rather
than leaving it to the users to find each other, Toutiao uses underlying algorithms to help enable meaningful
connections. Nowhere is this more relevant than in its recently developed question-and-answer feature, where the AI team
was tasked with developing a matching engine that links a question-asker with someone who can answer them. Toutiao
recently published a [paper](http://aclweb.org/anthology/P16-1076) for the ACL conference touting these results. Their
proposed “Conditional Focused Neural Question Answering with Large-Scale Knowledge Bases approach” achieves an accuracy
of 75.7% on a data set of 108K questions, and outperforms the current state of the art (better than the Memory Network
and LTG-CNN methods on the benchmark dataset) by an 11.8% margin.

Toutiao’s underlying technology not only creates a better user experience, but also serves to strengthen the company’s
competitive moat. More compelling content and interactions meant users would spend more time on the platform, and the
more time they spent on the platform the better the use of algorithms became. The smarter the system is, the better it
can distribute content – and the more content creators it attracts. This, in turn, drives more users to the platform.
And thus is born a strong data network effect - the power of the system grows exponentially with the scale of the
system. There are competitors who have launched since then (especially after seeing Toutiao’s success), however it has
been difficult to match the accuracy and efficacy of the Toutiao recommendation engine leading to continued rapid growth
for Toutiao.

## 3\. From content aggregation to content destination

It is not uncommon to see apps strive to move from content aggregation to content destination. However it is extremely
challenging from a brand and creative strategy to make that happen. Here is how Toutiao did it. Toutiao offered two
significant benefits to content contributors over the platforms.

**Strong incentives via revenue sharing** that enabled writers to make money from very early on. In 2014, Toutiao rolled
out incentive programs to attract more content creators to the platform. These ranged from offering office space, tools,
minimum guarantees per month if they hit certain key milestones (e.g., \# of articles, read rates) to sharing revenue
via monetization. Toutiao began monetizing via ads since 2014 and this enabled revenue sharing opportunities with their
content contributors.

This was the function that launched Toutiao, but as it has grown, Toutiao has transitioned into a deeper platform for
content generation, consumption, and connections. Today, it hosts more than 800,000 Toutiaohao accounts – professional
media outlets, bloggers, and influencers who use the platform to share articles, images, and videos with Toutiao users .
It hosts many more users sharing short posts through Wei Toutiao. The result is the wide variety of content that Toutiao
hosts today ranging from news to stocks to science to relationships. Top 20 categories account for only 60% of the
content supply and no single category contributes over 10% of the content.

Below is an example of a variety of content that a user can choose from (the screenshot only displays the 40 of the 50+
channels users can choose from):

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-5-1.png" alt="Toutiao 5-1" width="1481" height="1400" class="aligncenter size-full wp-image-1101020" />](https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-5-1.png)

**Larger and more relevant audience** than other platforms that directly translated to increasing brand presence for
content contributors. Almost all contributors create and distribute content on all platforms. But for many contributors,
they have the ability to attract more traffic from Toutiao due to the strong recommendation engine. One example is "
欢子tv“ ( Huanzi TV). This creator creates short videos about folks' lives and customs in the countryside of China.
Each of his videos has an average of 700,000 views, while the views in his Wechat official account is less than 1/40 of
that on Toutiao. Toutiao has enabled the long tail of contributors to reach their most relevant audience more seamlessly
than any other platform in China.

## 4\. Unencumbered by formats

Instead of being stubborn about their core format (e.g., listicles, long form content and news), Toutiao was quick to
expand to other formats when the data suggested they should. In 2015, at the time where most video platforms in China
are focusing on long-form videos, Toutiao added video capability and started to support PGC short video content
(typically 1-5 mins) on its platform. Toutiao had observed an increase in supply of video content in 2014 as
connectivity and infrastructure had improved significantly by 2014. Additionally, Toutiao rolled out several incentive
programs to promote video content creation on its platform. The transition from text to image to video was similar to
what most US platforms have seen to date.

Later in March 2016, Toutiao launched Toutiao Video (which is now renamed to Watermelon Video), a separate PGC short
video app powered by the same algorithm engine as Toutiao. Similar to written content, the underlying algorithms
recommend the most relevant videos to users based on their interest graph. Toutiao is now the "go-to platform" for PGC
short video content. More than half of its 74 mins daily usage for each user is spent watching short-form videos and
Toutiao is close to exceeding 10 billion video views every day.

## 5\. Early monetization and alignment with product

Toutiao has reached unprecedented scale in revenue in a short time frame (5 years since launch and 3 years since they
began monetizing) and it is remarkable that they are doing it without leveraging any social graph or product purchase
history. Toutiao is on target to hit more than 15B RMB (\>$2.2B USD) in revenue this year - one of the fastest growing
apps in terms of revenue in the history of the internet.

<img src="https://blog.ycombinator.com/wp-content/uploads/2017/10/Toutiao-Blog-Post-Graphics_revenue.png" alt="Toutiao Revenue Growth" width="1569" height="1898" class="aligncenter size-full wp-image-1101028" />

Of the many things that Toutiao does, one element that is core to its model more than any other: it is good at
identifying what its users want to see. It is fitting, then, that its business model maps perfectly to that strength.
Toutiao generates revenue by matching relevant ads to users, using the same proprietary technology behind their content
targeting. This has three important benefits:

First, it reduced the impact of monetization on the user experience – and may have actually improved the experience\!
Users typically consider ads as intrusive and degrading to their experience, but ads aligned with user preferences are
less so. In serving ads that are highly relevant to a user’s interests, Toutiao in many ways acts as a product discovery
mechanism.

The second is that it increased the rates that Toutiao could charge advertisers. One of the key problems in advertising
is identifying how to selectively place your ads in front of the highest potential customers, and advertisers spend
countless hours and enormous sums of money trying to target effectively. Toutiao’s technology, which solves this
targeting problem natively, represented a solution and saves advertisers from paying a big premium for it.

Third, since the primary use case is to read and view content, users are more receptive to seeing relevant targeted ads
and therefore there is more inventory available to advertisers.

The combination of all these three factors results in much better CTRs (Click Through Rates) on Toutiao vs. competitors.
Third party survey data estimates Toutiao’s CTRs to be 200% better than its peers.

**Impact on the Future of Content Discovery**

Toutiao is chipping away at their end goal, which is essentially to wipe away the concept of search and just serve up
aggregated, hyper-relevant content. We’ve seen “content aggregators” come and go in the U.S. but it is possible that
they are an idea whose time is yet to come – and that better algorithms will be the catalyst for success. Facebook and
Twitter are both critical sources for consumption of news in the U.S. today. The other giant in the room here is Google,
which in July announced that the feed in its mobile app would be increasing its use of machine learning to better show
their users the information they will find most relevant and interesting – a feed that incorporates all types of news.

-----

*Special thanks to the Toutiao team, Sharon Pope, Craig Cannon, Sonal Chokshi, Kat Manalac, Daniel Gross, and Ram
Parameswaran for reading multiple drafts of this essay.*

-----

\*About Bytedance

Founded in March 2012 in Beijing, Bytedance is at the global forefront of innovating artificial intelligence
technologies. Bytedance is dedicated to optimizing the connection of people with information, as well as promoting
content creation and communications. Its flagship product, Toutiao, is the largest AI-powered content discovery platform
in China, it delivers personalized content recommendations to every user based on their interests. Bytedance owns a
series of products celebrated by the users around the world, including Topbuzz, Flipagram and a series of UGC short
video apps.

Bytedance established an AI Lab in 2016, leveraging extensive and complex datasets to conduct state-of-the-art research
in artificial intelligence.

-----

**Notes**  
<b id="footnote1">1.</b> Source: Facebook Q1 2016 Earnings Call.[↩](#footnoteid1)  
<b id="footnote2">2.</b> Source:
<http://time.com/4272935/snapchat-users-usage-time-app-advertising/>.[↩](#footnoteid2)  
<b id="footnote3">3.</b> Source:
<http://www.businessinsider.com/china-has-more-smartphone-users-than-us-brazil-and-indonesia-combined-2015-7>.[↩](#footnoteid3)  
<b id="footnote4">4.</b> Source:
<https://www.statista.com/statistics/315485/china-number-of-mobile-apps-available/>.[↩](#footnoteid4)

