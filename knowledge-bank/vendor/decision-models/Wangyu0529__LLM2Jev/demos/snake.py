"""Play Snake with one LLM2Jev Choice question per tick.

Inspired by https://github.com/hwfengcs/any2jev/blob/main/examples/snake.py

    llm2jev-serve --model-path /path/to/model --served-model-name qwen --submission all
    python demos/snake.py local-model

Add ``--gif snake.gif`` when you want to save a GIF:

    python demos/snake.py local-model --gif snake.gif

The game owns the rules. The model only chooses between legal moves.
"""

from __future__ import annotations

import argparse
import http.client
import json
import random
import sys
import time
from urllib.parse import urlsplit


DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
INSTRUCTIONS = "Which direction should the snake move next to reach the food without hitting a wall or itself?"


class Snake:
    def __init__(self, width=12, height=10, seed=0):
        self.width, self.height, self.rng = width, height, random.Random(seed)
        self.body = [(width // 2, height // 2), (width // 2 - 1, height // 2)]
        self.direction = "right"
        self.food = self._spawn()
        self.score, self.steps, self.alive = 0, 0, True

    def _spawn(self):
        occupied = set(self.body)
        free = [(x, y) for x in range(self.width) for y in range(self.height) if (x, y) not in occupied]
        return self.rng.choice(free)

    def legal(self):
        moves = {}
        head_x, head_y = self.body[0]
        for direction, (dx, dy) in DIRS.items():
            if direction == OPPOSITE[self.direction]:
                continue
            destination = head_x + dx, head_y + dy
            x, y = destination
            if 0 <= x < self.width and 0 <= y < self.height and destination not in self.body[:-1]:
                moves[direction] = destination
        return moves

    def state(self, legal):
        head_x, head_y = self.body[0]
        food_x, food_y = self.food
        return {
            "board": {"width": self.width, "height": self.height},
            "head": {"x": head_x, "y": head_y},
            "food": {"x": food_x, "y": food_y},
            "food_direction": {
                "horizontal": "right" if food_x > head_x else "left" if food_x < head_x else "same column",
                "vertical": "down" if food_y > head_y else "up" if food_y < head_y else "same row",
            },
            "current_direction": self.direction,
            "length": len(self.body),
            "danger": {
                direction: "blocked"
                for direction in DIRS
                if direction not in legal and direction != OPPOSITE[self.direction]
            },
        }

    def step(self, direction, destination):
        self.steps += 1
        self.direction = direction
        self.body.insert(0, destination)
        if destination == self.food:
            self.score += 1
            self.food = self._spawn()
        else:
            self.body.pop()

    def render(self):
        grid = [["." for _ in range(self.width)] for _ in range(self.height)]
        for x, y in self.body[1:]:
            grid[y][x] = "o"
        head_x, head_y = self.body[0]
        food_x, food_y = self.food
        grid[head_y][head_x] = "O"
        grid[food_y][food_x] = "*"
        return "\n".join("".join(row) for row in grid)


class Client:
    """Persistent System One client; avoids reconnecting on every tick."""

    def __init__(self, api_base, model):
        url = urlsplit(api_base)
        connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
        self.connection = connection_type(url.hostname, url.port, timeout=300)
        self.path = f"{url.path.rstrip('/')}/v1/systemone"
        self.model = model

    def choose(self, game, legal):
        if len(legal) == 1:
            direction = next(iter(legal))
            return direction, {direction: 1.0}

        body = json.dumps({
            "state": game.state(legal),
            "model": self.model,
            "questions": {"move": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": {direction: f"Move {direction}" for direction in legal},
            }},
        }, separators=(",", ":"))
        self.connection.request(
            "POST",
            self.path,
            body,
            {"Content-Type": "application/json", "Accept": "application/json"},
        )
        response = self.connection.getresponse()
        payload = json.loads(response.read())
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {payload}")
        answer = payload["answers"]["move"]
        if answer["choice"] not in legal:
            raise RuntimeError(f"model selected illegal direction {answer['choice']!r}")
        return answer["choice"], answer["probabilities"]

    def close(self):
        self.connection.close()


def _save_gif(frames, path, cell=26, header=54, footer=62):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError("GIF export requires Pillow: pip install pillow") from error

    def font(size):
        try:
            return ImageFont.truetype("DejaVuSansMono.ttf", size)
        except OSError:
            return ImageFont.load_default()

    width, height = frames[0]["width"], frames[0]["height"]
    image_width, image_height = width * cell + 20, header + height * cell + footer
    images = []
    for frame in frames:
        image = Image.new("RGB", (image_width, image_height), "#111815")
        draw = ImageDraw.Draw(image)
        draw.text((10, 8), "LLM2Jev plays Snake", fill="#f2f6f4", font=font(18))
        draw.text((10, 32), f"score {frame['score']}  step {frame['step']}  {frame['ms']:.0f} ms", fill="#9caaa3", font=font(13))
        for y in range(height):
            for x in range(width):
                draw.rectangle((10 + x * cell, header + y * cell, 8 + (x + 1) * cell, header - 2 + (y + 1) * cell), fill="#26312c")
        for index, (x, y) in enumerate(frame["body"]):
            draw.rectangle(
                (10 + x * cell, header + y * cell, 8 + (x + 1) * cell, header - 2 + (y + 1) * cell),
                fill="#a5f3cf" if index == 0 else "#37bd83",
            )
        food_x, food_y = frame["food"]
        draw.ellipse((14 + food_x * cell, header + 4 + food_y * cell, 4 + (food_x + 1) * cell, header - 6 + (food_y + 1) * cell), fill="#ff685f")
        bar_y = header + height * cell + 8
        for index, (name, probability) in enumerate(frame["probabilities"].items()):
            x = 10 + index * (image_width - 20) // 3
            selected = name == frame["choice"]
            draw.text((x, bar_y), f"{name} {probability:.2f}", fill="#f2f6f4" if selected else "#9caaa3", font=font(12))
            bar_width = (image_width - 20) // 3 - 10
            draw.rectangle((x, bar_y + 19, x + bar_width, bar_y + 28), fill="#303b36")
            draw.rectangle((x, bar_y + 19, x + int(bar_width * probability), bar_y + 28), fill="#37bd83" if selected else "#4c86c6")
        images.append(image)
    images += [images[-1]] * 10
    images[0].save(path, save_all=True, append_images=images[1:], duration=110, loop=0, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="Model name exposed by llm2jev-serve")
    parser.add_argument("--api-base", default="http://127.0.0.1:30000")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--gif", help="Optional output GIF path (requires Pillow)")
    args = parser.parse_args()

    game = Snake(seed=args.seed)
    client = Client(args.api_base, args.model)
    frames, latencies = [], []
    try:
        while game.alive and game.steps < args.steps:
            legal = game.legal()
            if not legal:
                break
            started = time.perf_counter()
            choice, probabilities = client.choose(game, legal)
            latency = (time.perf_counter() - started) * 1000
            latencies.append(latency)
            game.step(choice, legal[choice])
            sys.stdout.write(
                "\x1b[2J\x1b[H"
                f"{game.render()}\nscore {game.score}  step {game.steps}  {latency:.0f} ms  "
                + " ".join(f"{name}:{probability:.2f}" for name, probability in probabilities.items())
                + "\n"
            )
            sys.stdout.flush()
            if args.gif:
                frames.append({
                    "body": list(game.body), "food": game.food,
                    "width": game.width, "height": game.height,
                    "score": game.score, "step": game.steps, "ms": latency,
                    "probabilities": probabilities, "choice": choice,
                })
            if args.delay:
                time.sleep(args.delay)
    finally:
        client.close()

    middle = sorted(latencies)[len(latencies) // 2] if latencies else 0
    print(f"\nfinal score {game.score} in {game.steps} steps | median latency {middle:.0f} ms")
    if args.gif and frames:
        _save_gif(frames, args.gif)
        print(f"wrote {args.gif}")


if __name__ == "__main__":
    main()
