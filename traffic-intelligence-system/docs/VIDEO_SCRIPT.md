# YouTube Video Script — "Traffic Intersection Intelligence" (Target: ~2 min)

Format notes: talk over a screen recording of the terminal/CLI output and (optionally) the notebook charts. Timestamps are approximate — pace to how you naturally talk, don't rush to hit them exactly.

---

### [0:00–0:15] Hook + the problem
**(Visual: a photo or short clip of a congested Indian intersection, then cut to terminal)**

> "If you've ever sat at an Indian traffic signal watching a side street get a full green light with zero cars on it, while your road backs up for a kilometer — that's not bad luck. That's a fixed timer. Most signals don't know how much traffic is actually waiting. I built an agent that does."

### [0:15–0:35] What it is
**(Visual: README on screen, or `python -m traffic_intel.cli cities`)**

> "This is a Traffic Intersection Intelligence System. It simulates a 4-way intersection with realistic Indian traffic — two-wheelers, autos, buses, the works — across seven city profiles: Mumbai, Delhi, Bangalore, Chennai, Pune, and two generic tiers. And it runs two competing signal controllers on identical traffic: a normal fixed timer, and an adaptive agent."

### [0:35–1:00] The agent itself
**(Visual: `signal_control.py` scrolled briefly, or just keep talking over terminal)**

> "The adaptive controller is the agent. Every tick, it watches the queue length on all four approaches and decides: extend this green light, or yield to the busier side. It's about fifteen lines of decision logic — no black box, no GPU, just a perceive-and-act loop a city traffic engineer could actually read and trust."

### [1:00–1:30] The result — run it live
**(Visual: run `python -m traffic_intel.cli compare --city mumbai --minutes 50 --asymmetric --seed 1` live, or show the pre-recorded output)**

> "Here's the actual comparison — same traffic, same seed, fixed timing versus the adaptive agent. The busy road's wait time drops by almost ten percent. The side street's wait time goes up — and that's the honest part. This isn't a free win, it's the agent correctly prioritizing where the traffic actually is. That's exactly the trade-off a real demand-responsive signal makes."

### [1:30–1:50] How I built it / vibe coding moment
**(Visual: notebook bar chart of fixed vs adaptive wait times)**

> "I built this in a vibe-coding loop — describe the behavior, run it, check the real numbers, fix what's lying. Twice the numbers were wrong in ways that mattered: once because the agent was checking the queue too late to act on it, once because a hidden seeding bug meant my 'reproducible' tests weren't reproducible. Both only showed up because I ran it and looked, instead of trusting the first version that compiled."

### [1:50–2:00] Close
**(Visual: GitHub repo page)**

> "Full code, 42 passing tests, and a demo notebook are linked below. Thanks for watching."

---

## Shot list / B-roll checklist
- [ ] Intro clip: congested intersection (stock or your own city — keep it generic, no need to film anything risky)
- [ ] Terminal: `python -m traffic_intel.cli cities`
- [ ] Terminal: `python -m traffic_intel.cli compare --city mumbai --minutes 50 --asymmetric --seed 1` (let the output sit on screen for ~5s so viewers can read the table)
- [ ] Notebook: the fixed-vs-adaptive bar chart
- [ ] Final card: GitHub link + your name/handle

## Recording tips
- Record terminal output at a large font size (18–22pt) — it gets compressed hard on YouTube.
- Do the live command run in one take if you can; if it fails or stalls, cut to a pre-recorded successful run instead of waiting on camera.
- Keep narration ~150 words/minute; this script is ~330 words, which lands close to 2:00–2:15 at a natural pace — trim the "How I built it" section first if you need to cut for time.
