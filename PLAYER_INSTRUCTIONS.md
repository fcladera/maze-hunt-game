# PLAYER_INSTRUCTIONS.md — How to Play

You are a single pixel on a 100×100 grid. The outer border is a wall, and
obstacle lines radiate from the walls toward the center. Some cells hold
**coins** (spawned every 10 ticks). Each tick everyone's moves happen at
the same time. If two or more players end a tick on the same cell, the one
with the **higher life** survives; the others die. Your goal: **stay alive**
(and be the last one standing).

Two numbers define you:
- **motion_count** — how many directional moves you've made (your "history").
- **life** = `20 × coins − motion_count`. Each move costs 1 life; each coin
  gives +20 life. **Higher life wins collisions.** So moves make you weaker,
  coins make you much stronger.

The game is designed so that **grabbing coins is the key to winning**: a
coin (+20 life) lets you beat almost any camper. But every move you make
(including wall-bumps) costs 1 life — so move deliberately.

---

## 1. Join the game

```bash
curl -X POST http://SERVER/join -H 'content-type: application/json' \
     -d '{"user_name":"alice"}'
```

Response:
```json
{
  "auth_key": "rk7abc...",
  "player_id": 3,
  "position": [42, 17],
  "life": 0,
  "motion_count": 0,
  "coins": 0,
  "tick": 0,
  "board": { "width": 100, "height": 100,
             "obstacles": [[0,0],[0,1], "..."] },
  "coins_on_board": [],
  "config": { "tick_interval": 2.0, "coin_interval": 10, "coin_value": 20 }
}
```

- Save `auth_key` — it identifies you for every later call. Keep it secret.
- You spawn at a random free cell with **life = 0**.
- One life per name per round: once you die, that name can't rejoin this round.
- The board is always fully connected — every free cell is reachable (the
  server guarantees this at generation time).

## 2. Coordinates & directions

- `x` = column `0..99` (→ right), `y` = row `0..99` (↓ down). Position is
  `[x, y]`.
- The border (`x=0`, `x=99`, `y=0`, `y=99`) is wall — you cannot leave the
  `1..98` interior.

| direction    | aliases                 | move            | life cost |
|--------------|-------------------------|-----------------|-----------|
| `up`         | `u`, `north`, `n`       | y − 1           | 1         |
| `down`       | `d`, `south`, `s`       | y + 1           | 1         |
| `left`       | `l`, `west`, `w`        | x − 1           | 1         |
| `right`      | `r`, `east`, `e`        | x + 1           | 1         |
| `upleft`     | `ul`, `northwest`, `nw` | x−1, y−1        | 1         |
| `upright`    | `ur`, `northeast`, `ne` | x+1, y−1        | 1         |
| `downleft`   | `dl`, `southwest`, `sw` | x−1, y+1        | 1         |
| `downright`  | `dr`, `southeast`, `se` | x+1, y+1        | 1         |
| `stay`       | `none`, `hold`, `0`     | no move         | **0**     |

**`stay` is free** — it neither moves you nor costs life, exactly like not
sending a move. Prefer simply not sending a move if you want to stay put and
preserve life.

## 3. See the board

```bash
curl "http://SERVER/state?auth_key=rk7abc..."
```

You get, for the latest resolved tick `T`:
- `you`: your `position`, `motion_count`, `coins`, `life`, `alive`, and any
  pending move.
- `players`: every **alive** opponent with `name`, `position`, `motion_count`,
  `coins`, and `life`.
- `coins`: the list of coin cells currently on the board.
- `obstacles`: the full wall list (border + radial lines; grows only if the
  server enables `shrink`, which is off by default).
- `scoreboard`: everyone, alive or dead, with `life`, `motion_count`, `coins`.

You can see every opponent's **life**. That number is the whole game — use it.

## 4. Move

```bash
curl -X POST http://SERVER/move -H 'content-type: application/json' \
     -d '{"auth_key":"rk7abc...","direction":"up"}'
```

- You submit **one** direction for the current tick. The server resolves it
  with everyone else's at the next tick boundary; `/state` then reflects the
  new positions.
- Submitting again in the same tick **replaces** your choice (last one wins);
  it still costs at most **one** life for that tick (zero if the final choice
  is `stay`).
- Submitting **nothing** (or `stay`) keeps you in place for **free** — no
  motion, no life cost.
- Moving into a wall/border leaves you in place **but still costs 1 life**
  (and +1 motion). Don't bump walls carelessly.

## 5. Tick timing

The server advances the tick when **either** all alive players have moved **or**
a short interval (default 2 s) elapses. So:
- Your move only takes effect at the **next** tick. `/state` shows the last
  resolved tick, not your pending move.
- To act each tick, send a `/move` once per tick; you'll see the result in the
  next `/state`.

## 6. The survival rule (read carefully)

When the tick resolves, every player ends on some effective target cell (their
chosen neighbor, or their current cell if they didn't move / `stay` / were
blocked by a wall). For each cell:
- **1 player** on it → that player is fine.
- **2+ players** on it → collision: the player with the **highest life**
  survives; all others die. **Tie on life → everyone on that cell dies.**

This includes a mover landing on a player who stayed — they collide on the
stayer's cell, decided by life. Life for this comparison already includes the
−1 for the move you just made (if you made one); a stayer is compared at their
current life.

## 7. Coins (the key to winning)

- Every **10 ticks** (T=10, 20, 30, …) a coin appears on a random free
  cell (up to a small cap of simultaneous coins).
- If, after a tick's collisions, **exactly one alive player** is on a coin
  cell, that player captures it: `coins + 1` ⇒ **life + 20**.
- The capture happens *after* collisions. So if two players race onto a coin,
  they collide first (by current life) and only the single survivor claims the
  +20. Don't brawl over a coin unless you have the higher life.
- A coin's +20 is enormous — it's worth 20 moves. A player with one coin
  (life ~20) beats almost any non-coin player.

## 8. Strategy

- **Grab the coins.** This is the single most important goal. A coin is +20
  life — enough to win almost any collision. Be near a likely coin spawn as
  each 10-tick mark approaches, and be ready to move onto it.
- **Life is both health and score — higher is better.** Every move costs 1
  life; every coin gives 20. Don't move unless it's worth it. Sitting still
  (or `stay`) is free and preserves life.
- **Don't ram a higher-life player.** If an opponent has higher life than you,
  moving onto them means you die. Only attack players whose life is **lower**
  than yours.
- **Campers are now beatable.** A player who never moves has life 0. A single
  coin gives you life 20, so you can freely run over a life-0 camper. Pure
  camping is no longer a safe strategy once coins are in play — go get them.
- **Bait opponents into moving.** Every move they make lowers their life by
  1. Pressure and positioning matter; make them spend life while you save
  yours.
- **Late joiners start at life 0** — weak until they grab a coin. Don't fear
  them unless they're heading for a coin.
- **Swaps are safe.** If you move to an opponent's cell while they move to
  yours, you land on different cells — **no collision**; you pass through.
  Useful to escape without risking a fight.
- **Use walls and the border.** They block movement and can corner opponents
  or shield a flank. But bumping a wall still costs you 1 life.
- **Diagonals are efficient.** A diagonal covers ground in one move, same
  life cost as a cardinal step. Use them to reach coins or evade faster — but
  only when the saved distance is worth the life.
- **Watch the life board, not just positions.** Plan to *not* be where a
  higher-life opponent will end up, and *do* be where a lower-life opponent
  (or a coin) will be.
- **Ties kill both.** If your life equals an opponent's, a head-on collision
  kills you both. Either get strictly higher life (grab a coin) or avoid the
  fight.

## 9. Worked examples

1. **You win a race by life.** You (life 5) and Bob (life 2) both move into
   empty cell C. After your moves: you life 4, Bob life 1. Both on C → higher
   wins → **you survive, Bob dies**.
2. **A coin changes everything.** You (life 4) hold nothing; Cara (life 22,
   one coin) moves onto your cell while you stay. Cara life 21 vs you life 4 →
   **Cara survives, you die.** Reverse it: if *you* had the coin (life 24) and
   Cara (life 2) rammed you → you 24 vs Cara 1 → **you survive, Cara dies**.
3. **Campers lose to coin-holders.** Dave never moves (life 0). You grabbed a
   coin earlier (life 20) and move onto Dave's cell: you 19 vs Dave 0 → **Dave
   dies, you survive** (at life 19). Pure camping is dead once coins appear.
4. **Tie kills both.** You (life 4) and Eve (life 4) both move into C → both
   become life 3 → tie → **both die**, C is left empty.
5. **Contested coin.** A coin sits at C. You (life 6) and Frank (life 8) both
   move onto C. Collisions resolve first: Frank 7 vs you 5 → **Frank survives,
   you die**; Frank then captures the coin (life 27). Don't contest a coin
   against higher life — let them take it and outmaneuver them later, or grab
   it when uncontested.
6. **Wall bump.** You (life 5) move `up` into a wall → you stay put, life
   becomes 4 (motion_count +1). If nobody targets your cell, you're fine but
   you've spent 1 life for nothing.

## 10. Quick reference

```bash
# join
curl -X POST $URL/join -H 'content-type: application/json' -d '{"user_name":"alice"}'
# state (latest)
curl "$URL/state?auth_key=KEY"
# state (history)
curl "$URL/state?auth_key=KEY&tick=3"
# move
curl -X POST $URL/move -H 'content-type: application/json' \
     -d '{"auth_key":"KEY","direction":"upright"}'
# stay (free) — or just don't send a move
curl -X POST $URL/move -H 'content-type: application/json' \
     -d '{"auth_key":"KEY","direction":"stay"}'
```

Rules of thumb: **grab the coins every 10 ticks, keep your life high, never
ram a higher-life player, bait others into spending life, use diagonals and
walls, and prefer a free stay (no move) over a paid one.**
