# On starting a company from a hackathon project

**Author:** Tanay Tandon
**Type:** Essay
**URL:** https://www.ycombinator.com/library/4x-on-starting-a-company-from-a-hackathon-project


---

A couple years ago, [Athelas](https://athelas.com/) (YC S16) started as a proof-of-concept project built overnight at
[YC Hacks 2014](https://ychacks.devpost.com/submissions/25781-athelas). This month we started shipping our first devices
to patients and hospitals around the country. We learned a lot in the process and wanted to share a few thoughts here.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-1.png" alt="athelas-1" width="1500" height="477" class="aligncenter size-full wp-image-1098303" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-1.png)

The device is a low-cost imager that enables rapid blood diagnostics through computer vision instead of traditional
lab-based techniques. Going from a hacked together hardware prototype to shippable product (especially in the medical
field) was a progression in dimensionality at every stage, and it’s quite interesting now to look back at day 1.

The first version that began at the hackathon used a rubber piece and spherical magnifier attached to a smartphone
camera. A blood sample would be held (by a toilet paper roll) underneath, the camera would take a couple images, then
produce the computer vision rendered malaria cell counts. In design this is quite similar to a [van Leeuwenhoek
microscope](https://en.wikipedia.org/wiki/Antonie_van_Leeuwenhoek) (considered one of the earliest microscopes ever
built) which was used to see microorganisms for the first time in human history. There were a few examples of this
setup, and I spent the first couple hours of the hackathon getting it to work consistently on my phone.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-2.png" alt="athelas-2" width="1330" height="1016" class="aligncenter size-full wp-image-1098304" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-2.png)

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-4.png" alt="athelas-4" width="1262" height="680" class="aligncenter size-full wp-image-1098305" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-4.png)

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-5.png" alt="athelas-5" width="1268" height="718" class="aligncenter size-full wp-image-1098306" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-5.png)

*Above: A few excerpts from a writeup I did on Athelas a few months after the hackathon.*

The real focus of the hack was writing segmentation and template matching approaches, combined with a fast random forest
model implementation that learned to classify extracted versions of the Red Blood Cells (RBCs). Cell boundaries would be
recognized, then fed into the classier to identify whether a parasitical cell (like Malaria or Trypanosoma) was present.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-6.png" alt="athelas-6" width="1304" height="520" class="aligncenter size-full wp-image-1098308" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-6.png)

This made for a fun demo, where a sample slide would have malaria tagged in it, but a normal person’s blood would not.
While functioning and a neat trick, someone needed to be physically holding the camera in place, the slide had to be
moved around, with the lighting often being hard to fix. At the end of the day it was a nice experimental toy you might
see someone post as a video on Facebook.

But we were sure it could be more. The core idea was - if we made it broad-ranging and easy enough for anyone to use -
why not have a simple blood screen in every doctor’s office, nursing facility, or even home? After heading back to
school, this idea consumed us and we decided to continue it - but as a product - not just a demo. That meant creating an
automated blood processing mechanism to generate a stained peripheral smear, a more robust computer vision approach for
different cell types, automated mechanisms to image the whole sample without holding the slide in place, and most
importantly - clinical validation.

Deepika (my cofounder) worked to perfect the fast staining mechanism and come up with a way to coat them on plastic
strips that could be ready to use out of the box. She worked mostly in-lab, synthesizing dozens of versions of the stain
compound, and observing empirically the quality of cell rendering. The other side of this problem was ensuring that the
strip could easily be compressed to create a ‘monolayer’, or single layer of cells that enables statistically
representative imaging.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-7.png" alt="athelas-7" width="1064" height="635" class="aligncenter size-full wp-image-1098309" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-7.png)

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-8.png" alt="athelas-8" width="1338" height="826" class="aligncenter size-full wp-image-1098310" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-8.png)

*Above: An excerpt from “The marching velocity of the capillary meniscus in a microchannel”, a sample of work we
referenced when attempting to model the flow in our channel to generate a monolayer. This capillary design was
eventually shelved for a future iteration.*

In the meantime, I focused on building a higher resolution optical set up in a still cheap, but stand-alone device. As
such, we could focus on monitoring more prevalent cell-types like Leukocytes and Platelets (beyond just malaria). The
heart of it was an actuation system, coupled with gaussian edge autofocusing algorithms to ensure that our cells were
being captured in a consistent fashion. Here’s a prototype midway through:

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-9.png" alt="athelas-9" width="536" height="504" class="aligncenter size-full wp-image-1098311" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-9.png)

Furthermore, we started assembling a training set of data from public CDC images, blood smears collected from
researchers at Stanford and UCSF - often hand labeled by me or a pathologist. From there, we were able to employ
traditional computer vision and deep learning approaches to recognize and classify cell types based on previous,
human-guided examples.

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-10.png" alt="athelas-10" width="1184" height="792" class="aligncenter size-full wp-image-1098312" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-10.png)

*Cell body extraction post hough transform, first pass, pre-segmentation and classification*

The first set of progress was slow. College workload at Stanford + rising costs of our hardware iterations often made it
difficult for us to operate with the iteration speeds a normal product needs. Finals often meant days going by without
any tangible progress whatsoever. But we put together a tangible, usable v1, that could grab images of a stained blood
sample, and process. [See the demo here](https://www.youtube.com/watch?v=fEcx3hx-398).

Then this summer, things came full circle to that orange building in Mountain View, as we joined the summer batch at Y
Combinator. Our time (now full time on the project) was focused on our clinical validation locally and at the FEMAP
family hospital, to run a first set of usages within a hospital system. The goal was proving the system on just one
aspect first: White Blood Cell counts. By grabbing images of samples on our strip, and then running the algorithms we
showed how our counts were correlating with high accuracy to the gold standard Beckman Counter across 350 patients,
combined with [a set of bench precision studies](http://athelas.com/data).

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-11.png" alt="athelas-11" width="1181" height="823" class="aligncenter size-full wp-image-1098313" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-11.png)

An interesting aspect was showing how our drop to drop precision [(something of much recent
interest)](https://www.jci.org/articles/view/86318) was clinically acceptable versus other systems operating on drops.
Coulter counters (traditional cell counting systems) work by flowing particles through a jeweled aperture a few microns
in diameter, and recording impedance to register particle size - and as a result, particle classification. At the crux
of it, [higher impedance = larger particle size](http://www.cyto.purdue.edu/cdroms/cyto2/6/coulter/ss000103.htm).

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-12.png" alt="athelas-12" width="210" height="367" class="aligncenter size-full wp-image-1098314" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-12.png)

Coulter Counting Principle diagram source: [cyto.purdue.edu](http://cyto.purdue.edu)

Athelas’s computer vision approach, however, focuses wholly on the image and nucleation patterns. As such, the
particulate matter or lymph that can often confuse a Coulter system (especially in diluted quantities), is simply
classified by the vision as a non-leukocyte cellular body (not a white blood cell, but some other, un-classified
artifact in the blood sample).

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-13.png" alt="athelas-13" width="743" height="313" class="aligncenter size-full wp-image-1098315" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-13.png)

The trial showed high inter-rater agreement (100% 5-class inter rater agreement) between the two systems, we submitted
our data off to the FDA for Class 2 510k approval, and are now distributing our Class 1 version of the system for rapid
White Blood Cell monitoring. See more at [athelas.com](http://athelas.com).

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-14.png" alt="athelas-14" width="600" height="371" class="aligncenter size-full wp-image-1098316" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-14.png)

[<img src="https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-15.png" alt="athelas-15" width="1181" height="1600" class="aligncenter size-full wp-image-1098317" />](https://blog.ycombinator.com/wp-content/uploads/2017/01/athelas-15.png)

As we integrate new blood tests into the system over the coming months (concussion monitoring, inflammation tracking,
urinary tract infection, platelets, more cell counts), our key growing challenge will be working with the existing
clinical and medical community to help guide adoption and usage. These coming months will focus on getting our $250
devices into as many point-of-care locations, homes, and clinical settings as possible.

We’re always looking for awesome people to meet and hackers to join our growing team, so shoot me an email if you want
to chat about anything: tanay \[at\] getathelas.com

