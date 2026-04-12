import { useState } from "react";
import { Copy, CheckCircle, ChevronLeft, ChevronRight, Download, ExternalLink } from "lucide-react";

const POSTS = [
  {
    id: 1,
    theme: "THE VISION",
    title: "Building India's Largest Hearing Care Network",
    infographic: "/infographics/hc_post1_vision.png",
    content: `We're standing on the brink of a hearing care revolution in India.

63 million Indians live with disabling hearing loss, yet only 5-7% use hearing aids. In contrast, developed countries help 30% of their hearing-impaired populations. Why the gap? A disorganized industry lacking clinical standards and comprehensive care.

Over 90% of our market is made up of mom-and-pop shops, functioning without standardized diagnostic equipment, protocols, or follow-up systems. We're here to change that.

At HearClear, we've planted the seeds of transformation with 40+ clinics across North India. Ambitious? Absolutely. Necessary? More than ever.

India's aging population is climbing. WHO has proven the direct link between hearing loss and a 5x higher risk of dementia. The time is NOW.

Our vision isn't to merely sell hearing aids. We're creating a comprehensive hearing care institution. With an AI-powered clinical-grade test that's 98% accurate in under 10 minutes, and a robust full-service stack, we offer a complete care experience our patients cannot find elsewhere.

Today we stand at 40 clinics. Tomorrow the target is 500-600. Imagine India with true hearing care access — based on clinical-grade infrastructure, proper diagnostics, and real rehabilitation programs — in every major city and beyond.

We're looking for collaborators who want to be part of this journey — from investors who see the potential for scale, to ENT specialists ready to partner for real patient outcomes.

Let's create a benchmark in Indian healthcare that checks off all the boxes.

#HearingCareRevolution #HealthcareTransformation #India2030 #InvestInHealth #ENTCollaboration #HearClearGrowth`
  },
  {
    id: 2,
    theme: "AI IN HEARING CARE",
    title: "Replacing 45-Min Booth Tests with 8-Min AI Diagnostics",
    infographic: "/infographics/hc_post2_ai.png",
    content: `The 45-minute soundproof booth test is going the way of the dinosaur.

At HearClear, we've transformed the hearing test experience with AI. Traditional methods require patients to sit for nearly an hour in a soundproof booth — far from inviting. That, plus their subjective nature, meant too many barriers to timely diagnosis.

Our AI-driven test flips the script. Delivering clinical-grade accuracy at 98% in just 8-10 minutes, it can be conducted in a clinic or right at home. We're screening 10x more patients every day and catching hearing loss far earlier — eliminating the "dreaded hospital visit" stigma entirely.

But let's be clear: AI isn't here to replace our skilled audiologists. It supercharges them. It's a powerful tool that allows us to direct resources where they're most effective, enhancing audiologist productivity and pinpointing misdiagnosis.

Looking to the future, the potential is enormous. AI paves the path toward predictive hearing health with personalized rehabilitation and continual remote monitoring. We're not just improving current practices, we're charting the course for what's possible.

This is not just a technological leap forward, it's a chance to redefine a customer experience steeped in simplicity and accuracy. It's about making hearing care as accessible and painless as it should be.

This is why HearClear is the leader in hearing care — spearheading a mission to make hearing care efficient, effective, and inclusive.

#AIInHealthCare #HearingTestRevolution #PatientExperienceMatters #SmartDiagnostics #FutureOfHealthcare #HearClearInnovation`
  },
  {
    id: 3,
    theme: "THE ECOSYSTEM PLAY",
    title: "Embedding into India's Healthcare Delivery",
    infographic: "/infographics/hc_post3_ecosystem.png",
    content: `In healthcare, you don't disrupt — you integrate.

HearClear isn't trying to outpace hospitals or ENT clinics. Instead, we're embedding right into their operations. Narayana Health and MAX@Home already recognize the value in leveraging our audiology expertise. This makes reliable audiology services a strength, not a stretch for them.

ENT doctors often refer patients to us, knowing we own the equipment and expertise they count on. With 100+ audiologists on our team, we're an extension of their practice, not competition.

We've brought hearing care into the elder care ecosystem through partnerships with EMOHA and 2050 Healthcare. It's as logical as offering dietitians and physiotherapists — hearing is critical to well-being. Healthians' collaboration ensures hearing checks are part of routine health checkups, embedding us deeply in preventive care.

Our insight? Hearing care shouldn't be an afterthought. We're interweaving it into every patient interaction point across healthcare. By building the audiology department hospitals and elder care providers can plug into, we're creating powerful referral loops and fortified partnerships.

The result? A system where each component bolsters the other, forming trust-based relationships that keep patients coming back. To the discerning investor, this isn't just strategy — it's defensibility. To the hospital CEO, it's a call to partnership.

Step into a value chain that makes sense — for patients, providers, and partners alike.

#HealthcareIntegration #StrategicPartnerships #AudiologyLeadership #HealthcareEcosystem #HearingCareConnectivity #HearClearHub`
  },
  {
    id: 4,
    theme: "CLINICAL DEPTH",
    title: "Not a Hearing Aid Shop — A Clinical Powerhouse",
    infographic: "/infographics/hc_post4_clinical.png",
    content: `In a market where "hearing care" often means little more than a hearing aid price tag, we're rewriting the narrative.

Most providers focus on transactions — we focus on transformations. HearClear isn't a hearing aid shop; it's a clinical powerhouse. From PTA and Impedance to OAE and BERA, our patients experience the full spectrum of diagnostics. Cochlear Implant referrals, speech therapy, tinnitus management — these aren't extras, they're mandates.

Our clinics are stocked with more than a tuning fork and a sales pitch. We've invested in top-tier diagnostic equipment, guaranteeing quality care at each location. With over 100 audiologists by our side — the largest private team in India — we ensure our experts are not only recruited but are consistently trained and retained.

Clinical depth creates trust. Patients might come to us thinking they'll leave with a device. Instead, they discover a path to lifelong care. ENTs trust us with their patients because they know our diagnostics are second to none.

We're diving into unserved areas like cochlear implants and vestibular disorders. These aren't just niches; they're needs — needs HearClear is positioned to fulfill.

This is our competitive advantage. You can't pluck 100 skilled audiologists and 40 well-equipped clinics out of thin air. This is our moat, built on clinical excellence and sustained by our unwavering commitment to patient care that goes beyond retail.

This isn't just what we do. It's who we are.

#ClinicalExcellence #HearingCareLeadership #PatientFirst #ENTTrust #AudiologyExcellence #LongTermCareInitiative`
  },
  {
    id: 5,
    theme: "CALL TO ACTION",
    title: "Join the Hearing Care Revolution",
    infographic: "/infographics/hc_post5_cta.png",
    content: `Are you ready to change the face of hearing care in India? Here's how you can join the mission.

Audiologists — We're hiring rockstars across India. Work with top brands like Signia, ReSound, Widex, Phonak, and Oticon using cutting-edge AI diagnostics. Join the largest audiology team in India. We're committed to your growth and success.

ENT Specialists — Partner with us for seamless referral pathways. Your patients receive world-class hearing care, and you benefit from a trusted follow-through. Let's redefine hearing healthcare together.

Hospitals — Looking to add audiology as a service line? We handle it all — from equipment to audiologists to training. You supply the space, we bring the expertise.

Healthcare Units & Clinics — Want a HearClear clinic in your facility? We are actively seeking partners in Tier 1 and Tier 2 cities to expand our network and impact.

Investors — The hearing care market in India is a $2B+ opportunity, growing at 15% YoY. If you're interested in elder care and healthcare infrastructure, let's have a conversation about shaping the future.

The need is now. Join us to build India's largest organized hearing care network. DM me or comment below. Let's build this together.

#JoinOurMission #HearingCareGrowth #AudiologyOpportunities #HealthcarePartnerships #InvestInHealth #HearClearExpansion`
  }
];

const HearClearPosts = () => {
  const [currentPost, setCurrentPost] = useState(0);
  const [copied, setCopied] = useState(false);

  const post = POSTS[currentPost];

  const handleCopy = () => {
    navigator.clipboard.writeText(post.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadImage = () => {
    const link = document.createElement("a");
    link.href = post.infographic;
    link.download = `HearClear_Post${post.id}_${post.theme.replace(/\s/g, "_")}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="hc-posts" data-testid="hearclear-posts">
      <div className="hc-posts-header">
        <h2>HearClear India — Strategic LinkedIn Posts</h2>
        <div className="hc-posts-nav">
          <button
            className="hc-nav-btn"
            disabled={currentPost === 0}
            onClick={() => setCurrentPost(currentPost - 1)}
            data-testid="prev-post-btn"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="hc-post-counter">
            Post {currentPost + 1} of {POSTS.length}
          </span>
          <button
            className="hc-nav-btn"
            disabled={currentPost === POSTS.length - 1}
            onClick={() => setCurrentPost(currentPost + 1)}
            data-testid="next-post-btn"
          >
            <ChevronRight size={20} />
          </button>
        </div>
      </div>

      <div className="hc-post-theme">{post.theme}</div>
      <h3 className="hc-post-title">{post.title}</h3>

      <div className="hc-post-layout">
        {/* Infographic */}
        <div className="hc-infographic-container">
          <img
            src={post.infographic}
            alt={`HearClear ${post.theme} infographic`}
            className="hc-infographic"
            data-testid={`infographic-${post.id}`}
          />
          <button className="hc-download-img-btn" onClick={handleDownloadImage} data-testid="download-infographic-btn">
            <Download size={14} /> Download Infographic
          </button>
        </div>

        {/* Post Content */}
        <div className="hc-post-content-area">
          <div className="hc-post-text" data-testid={`post-content-${post.id}`}>
            {post.content}
          </div>
          <div className="hc-post-actions">
            <button
              className={`hc-copy-btn ${copied ? "copied" : ""}`}
              onClick={handleCopy}
              data-testid="copy-post-btn"
            >
              {copied ? <><CheckCircle size={14} /> Copied!</> : <><Copy size={14} /> Copy Post</>}
            </button>
          </div>
        </div>
      </div>

      {/* Post Dots */}
      <div className="hc-post-dots">
        {POSTS.map((_, idx) => (
          <button
            key={idx}
            className={`hc-dot ${idx === currentPost ? "active" : ""}`}
            onClick={() => setCurrentPost(idx)}
            data-testid={`post-dot-${idx}`}
          />
        ))}
      </div>
    </div>
  );
};

export default HearClearPosts;
