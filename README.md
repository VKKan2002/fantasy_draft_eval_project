# Fantasy Football Lineup Assistant

Every week during the NFL season, fantasy football managers have to decide who to start
and who to bench. Doing it properly means checking injury reports, practice updates,
who your player is up against, betting lines, and how he's been playing lately — across
half a dozen websites, for a dozen players.

This does that for you and emails you the answer, with a reason for every call.

**But first it answers a question nobody selling these tools seems to ask: how much can a
tool like this actually help?**

---

## The honest answer

We checked twelve years of real fantasy leagues — 144 team-seasons — to find the ceiling.

**About 3 points a week, out of roughly 96.**

That's the gap between a simple rule anyone could follow and a cheater who knows the
future perfectly. Everything a tool could possibly do lives inside that 3 points.

Here's how a typical week breaks down:

| | Share of the decision |
|---|---|
| A simple rule already gets this right | 41% |
| Could be won with better information | **18%** |
| Pure luck — nobody can predict it | 40% |

![How much room is there for a smarter start/sit assistant?](docs/step1_headroom.png)

Two things worth knowing that came out of the same check:

**Chasing last week's performance is worse than ignoring the season entirely.** Starting
whoever did well last week was the *worst* of the six approaches tested — worse than just
using preseason rankings and never updating them.

**You can't tell whether a tool like this works by using it.** The week-to-week swing is
so large you'd need about 53 seasons to separate a real improvement from noise. Playing one
season gives you one.

---

## So what's the point?

The value isn't better picks. It's that you don't spend twenty minutes on Sunday morning
with eight tabs open, and that every recommendation tells you where it came from.

**What it won't claim:** that it picks better than a simple rule. It doesn't. Neither does
anything else in this category — there just isn't room. Any app implying otherwise is
selling you something.

**What it does promise, and what we can actually prove:** it doesn't make things up.

That second one matters more than it sounds. The real danger with an AI assistant isn't
bad advice — it's advice that sounds authoritative and is quietly wrong. So a second AI
reviews every sentence the first one wrote and checks it against the actual data. Anything
it can't back up gets rewritten.

Unlike "are the picks good," this is something we can measure — the facts are right there
to compare against, and there are hundreds of sentences to check every week instead of one
season per year.

*That measurement hasn't been run yet. The number goes here when it exists, and not before.*

---

## What happens each week

1. A scheduled job wakes up and pulls each manager's roster from ESPN.
2. For every player it checks: bye week, injury status, recent games, opponent, betting line.
3. If someone's listed as questionable, it goes hunting for news — practice reports, what
   the coach said, whether the guy ahead of him is hurt.
4. It works out the best legal lineup from all of that.
5. It compares that to what you already have set.
6. An AI writes the reasons. A second AI fact-checks them.
7. You get an email — but only if something actually changed since last time.

**"Nothing to change" is a real answer here.** If your lineup is already what it would
recommend, it says so. If the difference is half a point, it tells you it isn't worth
bothering. And if nothing's changed since the last email, you don't get one.

Most weeks that's the honest answer. Other apps invent a reason to change something because
they need you opening the app. This one doesn't need anything from you.

---

## A couple of things that went wrong along the way

**81 players had their stats swapped with someone else's.** Frank Gore and his son Frank
Gore Jr. both play in the NFL. The first version of the name-matching code treated them as
the same person, so a Hall of Fame running back's season got credited to his son. It
happened 81 times across different players — and it never crashed, it just quietly gave
wrong answers.

**One analysis looked great and was completely useless.** A simple approach appeared to beat
real draft-market consensus. Checking what it would actually do revealed it would have
drafted nine quarterbacks with the first fifteen picks. You can only start one.

Both are the dangerous kind of bug: no error message, just plausible nonsense.

---

## Where things stand

| | |
|---|---|
| Measuring the ceiling | done |
| Data pipeline and quality checks | done |
| Lineup math | done |
| The AI fact-checker | next |
| News searching | not started |
| Pulling rosters from ESPN | not started |
| Sending email | not started |

The measurement is finished and the design is settled. The assistant itself is still being
built.

---

## More detail

- **[docs/DESIGN.md](docs/DESIGN.md)** — how it's built, the technical decisions and why,
  the stack, how to run it
- **[docs/FINDINGS.md](docs/FINDINGS.md)** — every number above, with the script that
  produced it
- **[archive/](archive/)** — four earlier versions of this project and why each was dropped

## License

None specified yet.
