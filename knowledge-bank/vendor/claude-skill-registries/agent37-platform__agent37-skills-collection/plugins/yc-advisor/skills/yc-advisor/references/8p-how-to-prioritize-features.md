# How to prioritize features

**Author:** Emmett Shear
**Type:** Essay
**URL:** https://www.ycombinator.com/library/8p-how-to-prioritize-features


---

There are three different mental frameworks for prioritizing building features I've seen that work to figure out what to
build next on your product: Built For Me, where you design a product for yourself as the most enthusiastic customer;
Switch To Us, where you design a product for a set of existing and potential customers you talk to directly; and Three
Numbers Matter, where you pick three measurable focus areas and iterate over time. In my experience startups progress
through each framework in order, one after another, as the type of challenge shifts.[ Justin.tv](http://justin.tv/) was
a Built For Me startup originally, as we had the idea we wanted to make a live reality TV show and built the underlying
technology for ourselves first. Twitch was Built For Me in the beginning in the same way, as the only part of[
Justin.tv](http://justin.tv/) I really personally enjoyed was the video game streaming. However when we started working
on Twitch in earnest, I relied primarily on Switch To Us because our primary customers were streamers and I wasn’t a
streamer. Later we developed a Three Numbers Matter approach that's driven most development since.

**Built for me:** You are the primary exemplar user of your own product

  - In many ways, the hardest thing to do is to "know thyself". That's exactly what this requires. You're an
    enthusiastic user of your own product. Deeply introspect and figure out what you wish it did instead. Build that.
    What would you find delightful or fun or useful? Make it happen\!
  - Works best when you truly do love your product. I managed the viewer side of the Twitch experience this way for a
    long time, because I really do love watching Twitch.
  - Works best for small teams. It's hard to communicate intuitive introspective understanding to other people. You can
    create a small team inside of a big company, but it's difficult to get even a medium-sized organization aligned with
    this approach.
  - Works best if you have good intuitive access to your desires. Some people find themselves wanting what they "should"
    want, rather than what they actually want. You need to be able to guess what you’ll truly actually want, not what
    you think you’re supposed to want. It’s important to note that “I think I want this because it’s what I believe I’m
    supposed to want” feels subjectively very much like “I want this”, because human introspection is very unreliable.

**Switch to us:** People are already doing the behavior you want elsewhere, you want them to do it with you instead.

  - Interview as 5-6 dedicated users each from your service, from each competing service, from closely-adjacent
    services. Ask them if they've tried your product, tried multiple products. I’ve included a list of potentially
    useful interview questions at the end of this document.
  - You'll wind up with 50 or so interviews. Categorize the responses and score them in a spreadsheet. Look for
    patterns. Consider doubling down on your strengths, and shoring up obvious weaknesses. Pick stuff that will drive
    switches to your product from competitors. Probably target one competitor at a time. Things you can build or change
    fast are much better than things that take a long time, because customers don’t care how hard something is to build
    just how effective it is for their problem. But don’t shy away from hard problems if that’s what’s necessary.
  - The key to running effective interviews is to use the interviews to understand the problem, and based on what you
    learn to generate ideas for solving it. Validating an idea you already have is an anti-goal. You can’t improve an
    idea through any amount of validation. The goal of this process is to have better ideas as much as it is to
    prioritize them. If you generate your ideas from the problems and opportunities your customers face, you’ll have
    better ideas and a stronger intuitive sense of their priority. I did a talk on how to do this effectively:[
    https://www.youtube.com/watch?v=qAws7eXItMk](https://www.youtube.com/watch?v=qAws7eXItMk)
  - Works best when your product is very important to your customers. Streamers on Twitch have strong opinions about
    what makes a good streaming service that they can articulate very clearly and where they can weight tradeoffs. They
    think like "prosumers" or "SMBs" rather than consumers. Vs. say SnapChat, where the average user may have no idea
    what it is about SnapChat that they like exactly. Why do I find reddit so addictive? The reddit PMs might know, but
    I certainly don't.
  - Works best when you're selling a better mousetrap, rather than inventing the mousetrap category. Twitch was a better
    mousetrap for streamers on other streaming services, we weren't inventing live streaming as a category. Wouldn't
    have worked for us at[ Justin.tv](http://justin.tv/) when there were no existing live streamers because we were the
    first live streaming service.

**Three numbers matter:** There are a few key drivers that make using your product better or worse.

  - Talk to your customers, look at the data, and identify the three most important qualities of the product for your
    customer. For Amazon, for example, the three drivers are lower prices, more selection of products, and faster/more
    reliable shipping. Amazon focuses on finding ways to drive down prices, add new categories of products or new
    versions of products, and improving the speed and convenience of shipping. Of course other things matter too, but
    ideas that move those three things are given priority for product progress. At Twitch, our three metrics are
    audience size, positive interactions, and money. Twitch focuses on ways to help streamers grow the size of their
    audience, interact with that audience in more fun and connected ways, and earn more money per viewer.
  - Three is a magic number for focus. The truth is that your product is complex and there are many things you need to
    improve and it’s always tempting to add focus areas. Empirically, three seems to be the maximum number of focus
    areas that people can keep in mind consistently. Think about how lists like “X, Y, and Z” feels natural, but “W, X,
    Y, and Z” does not.
  - You can have a bonus fourth focus area as well: Stuff You Have To Do. PCI compliance is usually not a company focus,
    but failing it as a payment processor will still kill you. Your product needs to stay up, enough downtime will kill
    you. You can probably think of dozens of more examples. This stuff needs to be done and should be done, but should
    not be included in the top level three metrics.
  - This approach tends to be recursive. There are 3 metrics that matter at the top level. Driving each of those metrics
    can be further decomposed, and each can have 3 sub-drivers.
  - You'll wind up with three areas of investment. Come up with a metric for each (these will evolve over time...revisit
    them every few months), and start trying to move it. Choose your split by intuition...maybe it's 33/33/33, maybe
    it's 50/25/25, depends if you think one area is more important right now.
  - Works best when people choose your product for measurable reasons (price, audience size, speed) and almost not at
    all when people choose your product for difficult-to-measure ones (fun, connection, love, community). Good for
    making utilitarian things, less good for making games and toys and beautiful UX.
  - Operational excellence (good uptime, efficient use of employee labor, security, etc) is important for every company.
    But for a startup, it’s rare that you can win through pure operational excellence. Usually you need to do just
    enough operational excellence that it’s acceptable to your customers, and then focus on delivering on what your
    customers really care about. Sometimes one of the primary values for your company is that it’s low latency, or high
    security, or super reliable, and that aspect of operational excellence becomes a key goal. But even then, most
    aspects of operational excellence need to be run on a “good enough” basis early on.

While Twitch has been running primarily on a Three Numbers Matter approach, we go back to Switch To Us periodically for
new customer segments. For example, as we started working to launch our new music category, we started talking to
artists who livestreamed elsewhere online to understand what their needs were. Solving for those needs drove our
roadmap, rather than a metric driven Three Numbers Matter approach. As the category grows, we have begun to identify the
set of metrics that matter most for us and we will begin to transition towards Three Numbers Matter instead.

Certain problems don't fit any of these frameworks. What do you do if you're building a brand new mousetrap, which
people like your product for difficult-to-measure reasons, and you're not the end-user of it yourself? It's really
really hard\! So these constrain the space of problems where it's possible to build good stuff reliably. This constrains
big companies more than small ones, due to the difficulty of scaling up Built For Me. So you either find big companies
working on products where the important drivers are easy to measure, or you find them working on incremental innovation
in existing categories. Unless of course, the CEO is the lead designer like Steve Jobs at Apple, where you get a big
company escaping the dilemma and doing ground-breaking category creation for a product that's great for
difficult-to-measure reasons. The ongoing popularity of “hack day” or “hack week” within larger organizations fits into
this framework as well. Hack week is all about unleashing the Built For Me capacity latent inside any organization, by
reverting to a more startup-like approach with small teams and intuitive decisions. This also explains why a lot of the
biggest startups (though certainly not all) started with the Built For Me approach. It gives you an automatic advantage
against big incumbents who can't use the same method.

**Good Interview Questions for Switch To Us:**

  - What do you like about your current solution?
  - What don’t you like about it?
  - How did you wind up choosing your current solution?
  - What were you doing before?
  - What would you do if you were the CEO of the current company’s product you’re using?
  - What’s the single most annoying thing about your current solution?
  - What’s the single coolest new thing about your current solution?
  - Is there anything that would convince you to switch to using our product immediately if we built it? If so, what is
    it?
  - If you had a magic wand and could create any experience you wanted in this area, how would it work?
  - What’s one thing about your current solution that’s surprisingly hard?
  - Remember to follow up with “interesting, tell me more” or “why is that?” or “can you elaborate?” as appropriate.
    People know more than they think they do, they just need a good interviewer to draw it out of them.

