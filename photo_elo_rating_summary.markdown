# Summary for Photo Elo Rating System

## Objective
We are developing a photo management app to help users decide which photos to delete from a collection by assigning each photo a quantile rank (0 to 100, where 50 is the median) based on user preferences via pairwise comparisons. The goal is to identify photos in the bottom 10% of rankings with 90% confidence and mark them for deletion, excluding them from future comparisons to reduce user effort.

## Approach
- **Elo-Based Ranking**: Use a modified Elo rating system to rank photos, where users compare pairs of photos ("Which is better?") to update ratings.
- **Logistic Scale**: Represent each photo’s strength with an unbounded skill parameter \( s \), mapped to a quantile rank \( R \) (0-100) using:
  \[
  R = 100 \cdot \frac{1}{1 + e^{-s}}
  \]
  Initial \( s = 0 \) corresponds to \( R = 50 \).
- **Dynamic Confidence (\( k \))**: Instead of a static update constant, use a dynamic \( k_i \) per photo, reflecting uncertainty based on the number of comparisons (\( c_i \)):
  \[
  k_i = \frac{k_0}{\sqrt{c_i + 1}}
  \]
  where \( k_0 = 1 \) is the base confidence, tuned to the logistic scale.
- **Skill Updates**: After a comparison (e.g., photo A beats B), update skills:
  \[
  s_A' = s_A + k_A \cdot (1 - E_A), \quad s_B' = s_B + k_B \cdot (0 - E_B)
  \]
  where \( E_A = \frac{1}{1 + e^{-(s_A - s_B)}} \).
- **90% Upper Bound**: Calculate the 90% upper bound quantile to determine if a photo is confidently in the bottom 10%:
  \[
  s^{\text{upper}} = s + 1.645 \cdot k, \quad R^{\text{upper}} = 100 \cdot \frac{1}{1 + e^{-s^{\text{upper}}}}
  \]
  If \( R^{\text{upper}} \) is below the bottom 10% threshold, mark the photo for deletion.
- **Data Storage**: Store only \( s_i \) (skill) and \( c_i \) (comparison count) per photo, computing \( k_i \), \( R_i \), and \( R_i^{\text{upper}} \) on demand.

## Direction
- Focus on maintaining two values per photo: skill (\( s \)) and comparison count (\( c \)), with \( k \) derived dynamically.
- Use \( k_i = \frac{k_0}{\sqrt{c_i + 1}} \) to ensure larger updates early (when \( c_i \) is low) and smaller updates as confidence grows.
- Periodically compute \( R_i^{\text{upper}} \) to flag photos for deletion when they’re confidently in the bottom 10%.
- Future steps include tuning \( k_0 \), simulating comparisons, and integrating with a UI for user-friendly pairwise comparisons.

## Code Snippet
Below is a Python implementation of the skill update and quantile calculations:

```python
import math

def update_skills(s_a, s_b, c_a, c_b, outcome, k_0=1):
    """Update skills and comparison counts. Outcome: 1 (A wins), 0 (B wins)."""
    k_a = k_0 / math.sqrt(c_a + 1)
    k_b = k_0 / math.sqrt(c_b + 1)
    e_a = 1 / (1 + math.exp(-(s_a - s_b)))
    e_b = 1 - e_a
    s_a_new = s_a + k_a * (outcome - e_a)
    s_b_new = s_b + k_b * ((1 - outcome) - e_b)
    return s_a_new, s_b_new, c_a + 1, c_b + 1

def skill_to_quantile(s):
    """Convert skill to quantile rank (0-100)."""
    return 100 / (1 + math.exp(-s))

def upper_bound_quantile(s, c, k_0=1):
    """Calculate 90% upper bound quantile."""
    k = k_0 / math.sqrt(c + 1)
    s_upper = s + 1.645 * k
    return 100 / (1 + math.exp(-s_upper))
```