import pygame
from pygame.locals import *
import random
import json
import os

pygame.init()
screen = pygame.display.set_mode((300, 600))
pygame.display.set_caption("TSIS 3 Racer")
clock = pygame.time.Clock()

# Colors
WHITE = (255,255,255)
BLACK = (0,0,0)
RED = (255,0,0)
GREEN = (0,255,0)
BLUE = (0,0,255)
YELLOW = (255,255,0)
CYAN = (0,255,255)
GRAY = (128,128,128)

# Lane positions (5 lanes)
LANES = [47, 97, 147, 197, 247]

class Player(pygame.sprite.Sprite):
    def __init__(self, color="red"):
        super().__init__()
        try:
            self.image = pygame.transform.scale(pygame.image.load("DriverCar.png"), (45, 90))
        except:
            self.image = pygame.Surface((45, 90))
            self.image.fill(RED if color=="red" else BLUE if color=="blue" else GREEN)
        self.rect = self.image.get_rect()
        self.rect.center = (LANES[2], 525)
        self.lane = 2
    
    def left(self):
        if self.lane > 0:
            self.lane -= 1
            self.rect.centerx = LANES[self.lane]
    
    def right(self):
        if self.lane < 4:
            self.lane += 1
            self.rect.centerx = LANES[self.lane]

class Enemy(pygame.sprite.Sprite):
    def __init__(self, speed=4, lane=None):
        super().__init__()
        try:
            self.image = pygame.transform.scale(pygame.image.load("enemy_car.png"), (45, 90))
        except:
            self.image = pygame.Surface((45, 90))
            self.image.fill(RED)
        self.rect = self.image.get_rect()
        if lane is None:
            lane = random.randint(0, 4)
        self.rect.centerx = LANES[lane]
        self.rect.y = -90
        self.speed = speed
    
    def update(self):
        self.rect.y += self.speed
        return self.rect.y > 600

class Coin(pygame.sprite.Sprite):
    def __init__(self, lane, value=10):
        super().__init__()
        try:
            self.image = pygame.transform.scale(pygame.image.load("coin.png"), (20, 20))
        except:
            self.image = pygame.Surface((20, 20))
            self.image.fill(YELLOW)
        self.value = value
        self.rect = self.image.get_rect()
        self.rect.centerx = LANES[lane]
        self.rect.y = -30
    
    def update(self, speed):
        self.rect.y += speed
        return self.rect.y > 600

class PowerUp(pygame.sprite.Sprite):
    def __init__(self, lane, ptype):
        super().__init__()
        self.type = ptype
        try:
            self.image = pygame.transform.scale(pygame.image.load(f"{ptype}.png"), (25, 25))
        except:
            self.image = pygame.Surface((25, 25))
            if ptype == "nitro":
                self.image.fill(CYAN)
            elif ptype == "shield":
                self.image.fill(GREEN)
            else:
                self.image.fill(YELLOW)
        self.rect = self.image.get_rect()
        self.rect.centerx = LANES[lane]
        self.rect.y = -30
        self.life = 300
    
    def update(self, speed):
        self.rect.y += speed
        self.life -= 1
        return self.rect.y > 600 or self.life <= 0

class Hazard(pygame.sprite.Sprite):
    def __init__(self, lane, htype):
        super().__init__()
        self.type = htype
        self.image = pygame.Surface((25, 25))
        if htype == "oil":
            self.image.fill((50,50,50))
        elif htype == "pothole":
            self.image.fill((80,60,40))
        else:
            self.image.fill((139,69,19))
        self.rect = self.image.get_rect()
        self.rect.centerx = LANES[lane]
        self.rect.y = -30
    
    def update(self, speed):
        self.rect.y += speed
        return self.rect.y > 600

class Background:
    def __init__(self):
        try:
            self.img = pygame.transform.scale(pygame.image.load("road.png"), (300, 300))
        except:
            self.img = pygame.Surface((300, 300))
            self.img.fill((40,40,40))
            # Draw lane lines
            for i in range(1, 5):
                pygame.draw.line(self.img, WHITE, (i*60, 0), (i*60, 300), 2)
        self.y1 = 0
        self.y2 = -300
    
    def update(self, speed):
        self.y1 += speed
        self.y2 += speed
        if self.y1 >= 300:
            self.y1 = -300
        if self.y2 >= 300:
            self.y2 = -300
    
    def draw(self):
        screen.blit(self.img, (0, self.y1))
        screen.blit(self.img, (0, self.y2))

class Game:
    def __init__(self, name="Player", diff="normal", color="red", sound=True):
        self.name = name
        self.sound = sound
        self.running = True
        
        try:
            self.crash = pygame.mixer.Sound("honk.mp3") if sound else None
        except:
            self.crash = None
        
        speeds = {"easy":3, "normal":4, "hard":5}
        self.base_speed = speeds[diff]
        self.current_speed = self.base_speed
        self.enemy_speed = speeds[diff]
        
        self.player = Player(color)
        self.bg = Background()
        
        self.all = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.hazards = pygame.sprite.Group()
        self.all.add(self.player)
        
        # Track which lanes are occupied (for safe spawning)
        self.occupied_lanes = {i: False for i in range(5)}
        
        self.score = 0
        self.coins_total = 0
        self.distance = 0
        self.max_distance = 5000
        
        self.active_power = None
        self.power_time = 0
        self.shield = False
        
        self.spawn_timer = 0
        self.coin_timer = 0
        self.power_timer = 0
        
        # Spawn initial enemies with safe spacing
        for i in range(2):
            self.spawn_enemy_safe()
    
    def get_safe_lanes(self, avoid_lane=None):
        """Get list of lanes that are safe (no enemies in same lane nearby)"""
        safe = []
        for lane in range(5):
            if avoid_lane == lane:
                continue
            # Check if any enemy is in this lane and too close
            unsafe = False
            for e in self.enemies:
                if e.rect.centerx == LANES[lane] and e.rect.y < 400:
                    unsafe = True
                    break
            if not unsafe:
                safe.append(lane)
        return safe
    
    def spawn_enemy_safe(self):
        """Spawn enemy only in safe lane"""
        safe_lanes = self.get_safe_lanes()
        if safe_lanes:
            lane = random.choice(safe_lanes)
            e = Enemy(self.enemy_speed, lane)
            self.enemies.add(e)
            self.all.add(e)
            return True
        return False
    
    def spawn_coin_safe(self):
        """Spawn coin in random lane (coins are safe collectibles)"""
        lane = random.randint(0, 4)
        r = random.random()
        if r < 0.7: val = 10
        elif r < 0.9: val = 25
        else: val = 50
        c = Coin(lane, val)
        self.coins.add(c)
        self.all.add(c)
    
    def spawn_powerup_safe(self):
        """Spawn powerup in random lane"""
        lane = random.randint(0, 4)
        ptype = random.choice(["nitro", "shield", "repair"])
        p = PowerUp(lane, ptype)
        self.powerups.add(p)
        self.all.add(p)
    
    def spawn_hazard_safe(self):
        """Spawn hazard only in lane that has no enemy"""
        safe_lanes = self.get_safe_lanes()
        if safe_lanes:
            lane = random.choice(safe_lanes)
            htype = random.choice(["oil", "pothole", "barrier"])
            h = Hazard(lane, htype)
            self.hazards.add(h)
            self.all.add(h)
    
    def update_spawns(self):
        # Spawn enemies - less frequent and always safe
        self.spawn_timer += 1
        if self.spawn_timer > 45:  # Slower spawning
            if self.spawn_enemy_safe():
                self.spawn_timer = 0
        
        # Spawn coins frequently
        self.coin_timer += 1
        if self.coin_timer > 20:
            self.spawn_coin_safe()
            self.coin_timer = 0
        
        # Spawn powerups rarely
        self.power_timer += 1
        if self.power_timer > 350 and random.random() < 0.02:
            self.spawn_powerup_safe()
            self.power_timer = 0
        
        # Spawn hazards occasionally (always in safe lanes)
        if random.random() < 0.005:  # 0.5% chance per frame
            self.spawn_hazard_safe()
    
    def update_difficulty(self):
        mult = 1 + (self.distance / 4000)
        self.current_speed = self.base_speed + (mult - 1) * 1.5
        
        if self.active_power == "nitro" and self.power_time > 0:
            self.current_speed = min(10, self.current_speed + 3)
        
        self.enemy_speed = 3 + int(mult)
        for e in self.enemies:
            e.speed = self.enemy_speed
    
    def update_objects(self):
        # Update enemies
        for e in self.enemies:
            if e.update():
                e.kill()
                self.score += 50
        
        # Update coins
        for c in self.coins:
            if c.update(self.current_speed):
                c.kill()
        
        # Update powerups
        for p in self.powerups:
            if p.update(self.current_speed):
                p.kill()
        
        # Update hazards
        for h in self.hazards:
            if h.update(self.current_speed):
                h.kill()
    
    def check_collisions(self):
        # Enemy collision
        if pygame.sprite.spritecollideany(self.player, self.enemies):
            if self.shield:
                pygame.sprite.spritecollide(self.player, self.enemies, True)
                self.shield = False
                self.active_power = None
            else:
                if self.crash:
                    self.crash.play()
                return False
        
        # Collect coins
        for c in pygame.sprite.spritecollide(self.player, self.coins, True):
            self.score += c.value
            self.coins_total += 1
        
        # Collect powerups
        for p in pygame.sprite.spritecollide(self.player, self.powerups, True):
            if p.type == "repair":
                self.current_speed = self.base_speed
                self.score += 50
            elif p.type == "nitro":
                self.active_power = "nitro"
                self.power_time = 300
            elif p.type == "shield":
                self.active_power = "shield"
                self.power_time = 360
                self.shield = True
            self.score += 30
        
        # Hit hazards (only minor penalties)
        for h in pygame.sprite.spritecollide(self.player, self.hazards, True):
            if h.type == "oil":
                self.current_speed = max(2, self.current_speed - 2)
                self.score -= 5
            elif h.type == "pothole":
                self.current_speed = max(2, self.current_speed - 3)
                self.score -= 10
            elif h.type == "barrier":
                if not self.shield:
                    self.current_speed = max(2, self.current_speed - 4)
                    self.score -= 20
        
        return True
    
    def update_power(self):
        if self.active_power and self.power_time > 0:
            self.power_time -= 1
            if self.power_time <= 0:
                if self.active_power == "shield":
                    self.shield = False
                self.active_power = None
    
    def update_distance(self):
        self.distance += self.current_speed / 10
        self.score += int(self.current_speed / 2)
        return self.distance < self.max_distance
    
    def draw_ui(self):
        font = pygame.font.Font(None, 24)
        screen.blit(font.render(f"Score: {int(self.score)}", True, WHITE), (10,10))
        screen.blit(font.render(f"Coins: {self.coins_total}", True, YELLOW), (10,35))
        screen.blit(font.render(f"Dist: {int(self.distance)}", True, WHITE), (10,60))
        
        if self.active_power and self.power_time > 0:
            color = CYAN if self.active_power == "nitro" else GREEN
            txt = font.render(f"{self.active_power}: {self.power_time//10}s", True, color)
            screen.blit(txt, (10,85))
        
        if self.shield:
            screen.blit(font.render("SHIELD", True, GREEN), (220,10))
        
        # Show safe lanes indicator (helpful for new players)
        hint = font.render("Avoid red cars!", True, GRAY)
        screen.blit(hint, (10, 570))
    
    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    self.running = False
                if event.type == KEYDOWN:
                    if event.key in (K_LEFT, K_a):
                        self.player.left()
                    if event.key in (K_RIGHT, K_d):
                        self.player.right()
                    if event.key == K_ESCAPE:
                        self.running = False
            
            self.update_difficulty()
            self.update_objects()
            self.update_spawns()
            self.update_power()
            
            if not self.check_collisions():
                return self.score, self.distance, self.coins_total, False
            
            if not self.update_distance():
                self.score += 1000
                return self.score, self.distance, self.coins_total, True
            
            self.bg.update(self.current_speed / self.base_speed)
            
            screen.fill(BLACK)
            self.bg.draw()
            self.all.draw(screen)
            self.draw_ui()
            
            pygame.display.flip()
            clock.tick(60)
        
        return self.score, self.distance, self.coins_total, False

# ========== SAVE/LOAD ==========
def save_game(name, score, distance):
    try:
        scores = json.load(open("scores.json", "r")) if os.path.exists("scores.json") else []
    except:
        scores = []
    scores.append({"name": name, "score": int(score), "dist": int(distance)})
    scores.sort(key=lambda x: x["score"], reverse=True)
    json.dump(scores[:10], open("scores.json", "w"), indent=4)

def load_scores():
    try:
        return json.load(open("scores.json", "r"))
    except:
        return []

def save_settings(s):
    json.dump(s, open("settings.json", "w"), indent=4)

def load_settings():
    try:
        return json.load(open("settings.json", "r"))
    except:
        return {"name":"Player", "diff":"normal", "color":"red", "sound":True}

# ========== MENUS ==========
def name_input():
    name = ""
    font = pygame.font.Font(None, 36)
    while True:
        screen.fill(BLACK)
        screen.blit(font.render("Enter your name:", True, WHITE), (50,200))
        pygame.draw.rect(screen, WHITE, (50,250,200,40), 2)
        screen.blit(font.render(name, True, WHITE), (55,255))
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == QUIT:
                return "Player"
            if e.type == KEYDOWN:
                if e.key == K_RETURN and name:
                    return name
                if e.key == K_BACKSPACE:
                    name = name[:-1]
                elif len(name) < 15 and e.unicode.isprintable():
                    name += e.unicode

def main_menu():
    font = pygame.font.Font(None, 36)
    small = pygame.font.Font(None, 20)
    while True:
        screen.fill(BLACK)
        screen.blit(font.render("TSIS 3 RACER", True, YELLOW), (50,80))
        screen.blit(small.render("Avoid red cars - Collect coins - Use powerups", True, GRAY), (20,140))
        
        screen.blit(font.render("1 - Play", True, GREEN), (100,220))
        screen.blit(font.render("2 - High Scores", True, YELLOW), (100,280))
        screen.blit(font.render("3 - Settings", True, BLUE), (100,340))
        screen.blit(font.render("4 - Quit", True, RED), (100,400))
        
        screen.blit(small.render("Use A/D or LEFT/RIGHT to move", True, WHITE), (40,520))
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == QUIT:
                return "quit"
            if e.type == KEYDOWN:
                if e.key == K_1:
                    return "play"
                if e.key == K_2:
                    return "scores"
                if e.key == K_3:
                    return "settings"
                if e.key == K_4:
                    return "quit"

def scores_screen():
    scores = load_scores()
    font = pygame.font.Font(None, 24)
    while True:
        screen.fill(BLACK)
        screen.blit(font.render("TOP 10 RACERS", True, YELLOW), (70,50))
        
        y = 100
        for i, s in enumerate(scores[:10]):
            color = YELLOW if i == 0 else WHITE
            txt = f"{i+1}. {s['name']}: {s['score']} pts"
            screen.blit(font.render(txt, True, color), (50, y))
            y += 35
        
        if not scores:
            screen.blit(font.render("No scores yet!", True, GRAY), (90,250))
        
        screen.blit(font.render("Press ESC to return", True, GRAY), (70,550))
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == QUIT:
                return
            if e.type == KEYDOWN and e.key == K_ESCAPE:
                return

def settings_screen(settings):
    font = pygame.font.Font(None, 24)
    options = ["easy", "normal", "hard"]
    colors = ["red", "blue", "green", "yellow", "white"]
    
    while True:
        screen.fill(BLACK)
        screen.blit(font.render("SETTINGS", True, WHITE), (110,50))
        
        screen.blit(font.render(f"Difficulty: {settings['diff'].upper()}", True, WHITE), (50,150))
        screen.blit(font.render("[  Change  ]", True, GREEN), (180,150))
        
        screen.blit(font.render(f"Car Color: {settings['color']}", True, WHITE), (50,200))
        screen.blit(font.render("[  Change  ]", True, GREEN), (180,200))
        
        sound = "ON" if settings['sound'] else "OFF"
        screen.blit(font.render(f"Sound: {sound}", True, WHITE), (50,250))
        screen.blit(font.render("[  Toggle  ]", True, GREEN), (180,250))
        
        screen.blit(font.render("Press ESC to save", True, GRAY), (80,500))
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == QUIT:
                return settings
            if e.type == KEYDOWN and e.key == K_ESCAPE:
                return settings
            if e.type == MOUSEBUTTONDOWN:
                x, y = e.pos
                if 170 < x < 270:
                    if 140 < y < 170:
                        i = options.index(settings['diff'])
                        settings['diff'] = options[(i+1) % 3]
                    if 190 < y < 220:
                        i = colors.index(settings['color'])
                        settings['color'] = colors[(i+1) % 5]
                    if 240 < y < 270:
                        settings['sound'] = not settings['sound']

def game_over_screen(score, dist, coins, completed):
    font = pygame.font.Font(None, 30)
    while True:
        screen.fill(BLACK)
        if completed:
            screen.blit(font.render("★ RACE COMPLETE! ★", True, GREEN), (40,100))
        else:
            screen.blit(font.render("GAME OVER", True, RED), (80,100))
        
        screen.blit(font.render(f"Score: {int(score)}", True, WHITE), (90,200))
        screen.blit(font.render(f"Distance: {int(dist)}", True, WHITE), (80,240))
        screen.blit(font.render(f"Coins: {coins}", True, YELLOW), (95,280))
        
        screen.blit(font.render("R - Try Again    M - Menu", True, BLUE), (40,450))
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == QUIT:
                return "quit"
            if e.type == KEYDOWN:
                if e.key == K_r:
                    return "retry"
                if e.key == K_m:
                    return "menu"

def main():
    settings = load_settings()
    
    while True:
        action = main_menu()
        
        if action == "play":
            name = name_input()
            while True:
                game = Game(name, settings['diff'], settings['color'], settings['sound'])
                score, dist, coins, completed = game.run()
                save_game(name, score, dist)
                
                again = game_over_screen(score, dist, coins, completed)
                if again == "menu" or again == "quit":
                    break
                # if "retry", loop continues with new game
            
        elif action == "scores":
            scores_screen()
        
        elif action == "settings":
            settings = settings_screen(settings)
            save_settings(settings)
        
        elif action == "quit":
            break
    
    pygame.quit()

if __name__ == "__main__":
    main()