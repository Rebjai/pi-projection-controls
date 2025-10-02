import pygame
import requests
import io
import sys
import time
import threading

pygame.init()

# --- CONFIG ---
SERVER_URL = "http://localhost:5000"
UPLOADS_ENDPOINT = f"{SERVER_URL}/uploads"
UPLOADS_BASE_URL = f"{SERVER_URL}/uploads/"
SCREEN_W, SCREEN_H = 1000, 700
BG_COLOR = (30, 30, 30)
SLIDE_INTERVAL = 5.0

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.RESIZABLE)
SCREEN_W, SCREEN_H = screen.get_size()
pygame.display.set_caption("Dynamic Photo Gallery")
pygame.mouse.set_visible(False)

font = pygame.font.SysFont("Arial", 20)

# --- LOAD IMAGES ---
def fetch_image_list():
    try:
        r = requests.get(UPLOADS_ENDPOINT, timeout=10)
        r.raise_for_status()
        return r.json().get("uploads", [])
    except Exception as e:
        print("❌ Failed to fetch list:", e)
        return []

image_list = fetch_image_list()

def load_images_from_server():
    imgs = []
    for fname in image_list:
        url = UPLOADS_BASE_URL + fname
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            img = pygame.image.load(io.BytesIO(r.content)).convert()  # sin alpha para menos RAM
            imgs.append(img)
        except Exception as e:
            print(f"❌ Failed to load {url}: {e}")
    return imgs

images = load_images_from_server()
if not images:
    print("⚠️ No images found on server.")
    pygame.quit()
    sys.exit()

current_idx = 0
last_switch = time.time()
presentation_mode = False
carousel_offset = 0

# server actions
def show_image_on_server(image_name):
    """Send POST request to server to show the selected image."""
    def _send():
        try:
            print(f"➡️ Showing image on server: {image_name}")
            url = f"{SERVER_URL}/manual_show/{image_name}"
            requests.post(url, timeout=5)
        except Exception as e:
            print("❌ Failed to send manual_show request:", e)
    threading.Thread(target=_send, daemon=True).start()

# --- BUTTONS ---
class Button:
    def __init__(self, text):
        self.text = text
        self.rect = pygame.Rect(0, 0, 0, 0)

    def update_rect(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, surf):
        pygame.draw.rect(surf, (70, 70, 70), self.rect, border_radius=6)
        label = font.render(self.text, True, (255, 255, 255))
        surf.blit(label, label.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

btn_prev = Button("◀ Prev")
btn_next = Button("Next ▶")
btn_start = Button("Start ▶")
btn_stop = Button("■ Stop")
buttons = [btn_prev, btn_next, btn_start, btn_stop]

# --- HELPERS ---
def scale_to_fit(img, max_w, max_h):
    w, h = img.get_size()
    ratio = min(max_w / w, max_h / h)
    return pygame.transform.smoothscale(img, (int(w * ratio), int(h * ratio)))

def get_scaled_main(idx, W, H):
    """Escala solo la imagen actual al área principal."""
    control_h = int(H * 0.12)
    carousel_h = int(H * 0.18)
    main_h = H - (carousel_h + control_h)
    return scale_to_fit(images[idx], W * 0.9, main_h * 0.9)

def get_scaled_thumbs(W, H):
    """Escala thumbnails de todas las imágenes (solo una vez por tamaño de ventana)."""
    carousel_h = int(H * 0.18)
    thumb_h = int(carousel_h * 0.7)
    thumb_w = int(thumb_h * 4/3)
    return [scale_to_fit(img, thumb_w, thumb_h) for img in images]

scaled_thumbs = get_scaled_thumbs(SCREEN_W, SCREEN_H)

# --- MAIN LOOP ---
running = True
while running:
    screen.fill(BG_COLOR)
    W, H = screen.get_size()

    control_h = int(H * 0.12)
    carousel_h = int(H * 0.18)
    main_h = H - (carousel_h + control_h)

    # --- CAROUSEL ---
    thumb_w, thumb_h = scaled_thumbs[0].get_size()
    spacing = int(thumb_w * 0.2)
    y = main_h + int(carousel_h * 0.15)
    start_x = int(W * 0.05)

    thumb_rects = []


    # --- CAROUSEL ---
    for i, thumb in enumerate(scaled_thumbs):
        x = start_x + (i - carousel_offset) * (thumb_w + spacing)
        rect = pygame.Rect(x, y, thumb_w, thumb_h)
        screen.blit(thumb, rect)
        thumb_rects.append(rect)
        if i == current_idx:
            pygame.draw.rect(screen, (0, 200, 200), rect, 3)

    # --- ARROWS ---
    arrow_size = thumb_h // 2
    left_arrow = pygame.Rect(10, y + thumb_h//2 - arrow_size//2, arrow_size, arrow_size)
    right_arrow = pygame.Rect(W - arrow_size - 10, y + thumb_h//2 - arrow_size//2, arrow_size, arrow_size)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if btn_prev.is_clicked(pos):
                current_idx = (current_idx - 1) % len(images)
                show_image_on_server(image_list[current_idx])
            elif btn_next.is_clicked(pos):
                current_idx = (current_idx + 1) % len(images)
                show_image_on_server(image_list[current_idx])
            elif btn_start.is_clicked(pos):
                presentation_mode = True
                last_switch = time.time()
            elif btn_stop.is_clicked(pos):
                presentation_mode = False
            elif left_arrow.collidepoint(pos):
                carousel_offset = max(carousel_offset - 1, 0)
            elif right_arrow.collidepoint(pos):
                carousel_offset = min(carousel_offset + 1, len(images) - 1)
            else:
                for i, rect in enumerate(thumb_rects):
                    if rect.collidepoint(pos):
                        print(f"➡️ Thumbnail clicked: {image_list[i]}")
                        current_idx = i
                        show_image_on_server(image_list[current_idx])
                        break

    # slideshow auto-advance
    if presentation_mode and time.time() - last_switch >= SLIDE_INTERVAL:
        current_idx = (current_idx + 1) % len(images)
        show_image_on_server(image_list[current_idx])
        last_switch = time.time()

    # --- MAIN IMAGE ---
    main_img = get_scaled_main(current_idx, W, H)
    rect = main_img.get_rect(center=(W // 2, main_h // 2))
    screen.blit(main_img, rect)


    # --- DRAW ARROWS ---
    pygame.draw.polygon(screen, (255, 255, 255),
                        [(left_arrow.right, left_arrow.top),
                         (left_arrow.right, left_arrow.bottom),
                         (left_arrow.left, left_arrow.centery)])
    pygame.draw.polygon(screen, (255, 255, 255),
                        [(right_arrow.left, right_arrow.top),
                         (right_arrow.left, right_arrow.bottom),
                         (right_arrow.right, right_arrow.centery)])

    # --- CONTROLS ---
    btn_area_y = H - control_h + 10
    btn_w = W // (len(buttons) + 1)
    btn_h = control_h - 20
    for i, btn in enumerate(buttons):
        x = (i + 1) * btn_w - btn_w // 2
        btn.update_rect(x - btn_w // 4, btn_area_y, btn_w // 2, btn_h)
        btn.draw(screen)

    pygame.display.flip()
    pygame.time.delay(30)

pygame.quit()
