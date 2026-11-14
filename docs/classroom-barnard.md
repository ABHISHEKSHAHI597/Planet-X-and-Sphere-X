# Classroom activity: measure Barnard's Star with a ruler (optimisation.md IMP-5)

Ages 12 and up, 30–40 minutes, groups of two or three. Needs: a ruler, a calculator, and either a screen with
ParallaX open or two printed frames. No astronomy background needed.

**Teacher's preparation.** Open ParallaX on Barnard's Star at 12′ (`/?q=Barnard's%20Star&pin=21a7689afc4b&fov=12`)
and open the **25-year blink** panel. Print, or show one after the other, the oldest frame (2MASS, around 2000) and
the newest SPHEREx frame, at the same size. The 25-year blink is shown on the team's laptops today and on the public
site once its evidence gate is accepted (`/proof`); until then, prepare the two prints from a laptop.

## 1. Blink (5 min)
Flip between the two frames. Most dots stay put. One bright dot jumps. That is Barnard's Star: the star that crosses
our sky fastest. In 1930 Clyde Tombaugh found Pluto the same way, flipping between two photographs.

## 2. Measure (10 min)
1. On each frame, mark the centre of the jumping star with a small cross.
2. Lay the frames on top of each other (or hold them against a window) so the other stars line up. Measure the
   distance between the two crosses, in millimetres: **d** = ____ mm.
3. Measure the width of the picture, in millimetres: **W** = ____ mm. The picture is 12 arcminutes wide.
4. The jump in arcminutes is **12 × d / W** = ____′.

## 3. Work it out (10 min)
1. Years between the two frames (read the dates on the frames): **T** = ____ years.
2. Speed across the sky: **jump × 60 / T** = ____ arcseconds per year (1′ = 60″).
3. Compare with the catalogue: the Gaia satellite measured Barnard's Star moving **10.39″ per year**
   (Gaia DR3: 10.362″/yr north and 0.802″/yr west, combined). How close did you get? What limited you?

## 4. Think (10 min)
- The full Moon is about 30′ across. How many years until Barnard's Star has moved by one full Moon?
  (About 30 × 60 / 10.39 ≈ 170 years.)
- Barnard's Star is about 6 light-years away. Why do nearby stars seem to move faster than distant ones?
- Why does ParallaX compare frames taken in the same band only? (Hint: SPHEREx sees a different colour in each
  exposure. Would a star whose brightness depends on colour seem to flicker?)

## For the teacher
- Expected answer: 26 years × 10.39″/yr ≈ 270″ ≈ 4.5′, with the 2MASS epoch near 2000. Ruler answers within 10–20 %
  are good: the star is a blob a few millimetres wide on paper.
- Everything here is a measurement the students make themselves; ParallaX's own measured numbers, with their
  evidence records, are on its `/proof` page.
- To hand out as a PDF: `pandoc docs/classroom-barnard.md -o classroom-barnard.pdf`.
