import os
import sys
import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

# Import PyJNius for Android Java API bridge
from jnius import autoclass, cast

# Load Native Android Classes
PythonActivity = autoclass('org.kivy.android.PythonActivity')
Intent = autoclass('android.content.Intent')
Settings = autoclass('android.provider.Settings')
Uri = autoclass('android.net.Uri')
Context = autoclass('android.content.Context')
WindowManager = autoclass('android.view.WindowManager')
LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
PixelFormat = autoclass('android.graphics.PixelFormat')
View = autoclass('android.view.View')
TextView = autoclass('android.widget.TextView')
Color = autoclass('android.graphics.Color')
MotionEvent = autoclass('android.view.MotionEvent')
Toast = autoclass('android.widget.Toast')

# Import llama-cpp-python for local Gemma 1B inference
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False


class LocalGemmaEngine:
    """Manages local Gemma 1B execution on device."""
    def __init__(self, model_path):
        self.model_path = model_path
        self.llm = None
        
    def load_model(self):
        if LLAMA_AVAILABLE and os.path.exists(self.model_path):
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=1024,
                n_threads=4,
                verbose=False
            )
            return True
        return False

    def evaluate_text(self, text):
        if not self.llm:
            return "Error: Local Gemma 1B model not loaded."
        
        prompt = (
            f"<start_of_turn>user\n"
            f"Analyze the following article text for trustworthiness. "
            f"Rate it from 1 to 10 and give a short 2-sentence explanation.\n\n"
            f"Article Text: {text[:1000]}\n<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
        
        output = self.llm(
            prompt,
            max_tokens=120,
            temperature=0.2,
            stop=["<end_of_turn>"]
        )
        return output['choices'][0]['text'].strip()


class FloatingBubbleManager:
    """Handles the Android System Overlay Window (Floating Drag Bubble)."""
    def __init__(self, activity, gemma_engine):
        self.activity = activity
        self.gemma_engine = gemma_engine
        self.window_manager = cast(WindowManager, activity.getSystemService(Context.WINDOW_SERVICE))
        self.bubble_view = None
        self.params = None
        self.initial_x = 0
        self.initial_y = 0
        self.touch_start_x = 0.0
        self.touch_start_y = 0.0

    def show_bubble(self):
        # Configure layout overlay parameters
        self.params = LayoutParams(
            LayoutParams.WRAP_CONTENT,
            LayoutParams.WRAP_CONTENT,
            LayoutParams.TYPE_APPLICATION_OVERLAY,
            LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        )
        self.params.x = 0
        self.params.y = 100

        # Create a native TextView as the visual bubble UI
        self.bubble_view = TextView(self.activity)
        self.bubble_view.setText(" 🔍 Check Trust ")
        self.bubble_view.setTextSize(14.0)
        self.bubble_view.setTextColor(Color.WHITE)
        self.bubble_view.setBackgroundColor(Color.parseColor("#3F51B5"))
        self.bubble_view.setPadding(30, 20, 30, 20)

        # Attach touch listener for dragging and clicking
        self.setup_touch_listener()

        # Mount to Android Window
        self.window_manager.addView(self.bubble_view, self.params)

    def setup_touch_listener(self):
        class TouchListener(autoclass('android.view.View$OnTouchListener')):
            def __init__(outer_self):
                super().__init__()
                outer_self.manager = self

            def onTouch(outer_self, v, event):
                action = event.getAction()
                if action == MotionEvent.ACTION_DOWN:
                    outer_self.manager.initial_x = outer_self.manager.params.x
                    outer_self.manager.initial_y = outer_self.manager.params.y
                    outer_self.manager.touch_start_x = event.getRawX()
                    outer_self.manager.touch_start_y = event.getRawY()
                    return True
                
                elif action == MotionEvent.ACTION_MOVE:
                    outer_self.manager.params.x = outer_self.manager.initial_x + int(event.getRawX() - outer_self.manager.touch_start_x)
                    outer_self.manager.params.y = outer_self.manager.initial_y + int(event.getRawY() - outer_self.manager.touch_start_y)
                    outer_self.manager.window_manager.updateViewLayout(outer_self.manager.bubble_view, outer_self.manager.params)
                    return True
                
                elif action == MotionEvent.ACTION_UP:
                    diff_x = abs(event.getRawX() - outer_self.manager.touch_start_x)
                    diff_y = abs(event.getRawY() - outer_self.manager.touch_start_y)
                    if diff_x < 10 and diff_y < 10:
                        # Click detected: Extract screen text and run evaluation
                        outer_self.manager.process_screen_content()
                    return True
                return False

        self.bubble_view.setOnTouchListener(TouchListener())

    def process_screen_content(self):
        Toast.makeText(self.activity, "Analyzing page trust...", Toast.LENGTH_SHORT).show()
        
        # Scrape on-screen text via native Accessibility Tree
        text_content = self.extract_active_window_text()
        
        if not text_content:
            Toast.makeText(self.activity, "No screen text captured. Enable Accessibility Service.", Toast.LENGTH_LONG).show()
            return

        def run_inference():
            rating = self.gemma_engine.evaluate_text(text_content)
            
            # Show output toast on main UI thread
            def update_ui(dt):
                Toast.makeText(self.activity, f"Result: {rating}", Toast.LENGTH_LONG).show()
            Clock.schedule_once(update_ui)

        threading.Thread(target=run_inference).start()

    def extract_active_window_text(self):
        """Scrapes screen text node-by-node via active Android Window Hierarchy."""
        extracted_text = []
        try:
            AccessibilityService = autoclass('android.accessibilityservice.AccessibilityService')
            service = AccessibilityService.getSharedInstance()
            if service:
                root_node = service.getRootInActiveWindow()
                if root_node:
                    self._traverse_nodes(root_node, extracted_text)
        except Exception as e:
             print(f"Error reading UI nodes: {e}")
        return " ".join(extracted_text)

    def _traverse_nodes(self, node, text_list):
        if not node:
            return
        if node.getText():
            text_list.append(str(node.getText()))
        for i in range(node.getChildCount()):
            self._traverse_nodes(node.getChild(i), text_list)


class MainApp(App):
    def build(self):
        self.activity = PythonActivity.mActivity
        self.gemma = LocalGemmaEngine(model_path="/sdcard/Download/gemma-1b-it-q4_k_m.gguf")
        self.bubble_manager = FloatingBubbleManager(self.activity, self.gemma)

        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        self.status_label = Label(text="Gemma 1B Trust Evaluator", font_size='18sp')
        layout.add_widget(self.status_label)

        btn_start = Button(text="Start Floating Bubble", size_hint=(1, 0.2))
        btn_start.bind(on_press=self.start_services)
        layout.add_widget(btn_start)

        return layout

    def start_services(self, instance):
        # 1. Request Overlay Permission (SYSTEM_ALERT_WINDOW)
        if not Settings.canDrawOverlays(self.activity):
            intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            Uri.parse(f"package:{self.activity.getPackageName()}"))
            self.activity.startActivity(intent)
            return

        # 2. Load LLM Engine in background
        threading.Thread(target=self.load_model_and_show_overlay).start()

    def load_model_and_show_overlay(self):
        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', 'Loading Gemma 1B GGUF Model...'))
        loaded = self.gemma.load_model()
        
        def show_overlay(dt):
            if loaded:
                self.status_label.text = "Engine Active! Floating Widget Spawned."
            else:
                self.status_label.text = "Model GGUF missing in Downloads. Running in Fallback Overlay mode."
            self.bubble_manager.show_bubble()

        Clock.schedule_once(show_overlay)


if __name__ == "__main__":
    MainApp().run()
