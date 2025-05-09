import tweepy
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timezone, timedelta
import os
import logging
import threading
from dotenv import load_dotenv

client = None
logger = None

class GuiHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.configure(state='disabled')
        self.text_widget.see(tk.END)

def setup_logger(log_text_widget):
    logger_instance = logging.getLogger("TwitterDeleterGUI")
    logger_instance.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # print(f"DEBUG: setup_logger called. Current handlers for TwitterDeleterGUI: {logger_instance.handlers}")
    if not logger_instance.hasHandlers():
        # print("DEBUG: Adding new handlers to TwitterDeleterGUI")
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger_instance.addHandler(ch)
        gui_handler = GuiHandler(log_text_widget)
        gui_handler.setFormatter(formatter)
        logger_instance.addHandler(gui_handler)
    # else:
        # print("DEBUG: TwitterDeleterGUI already has handlers.")
    # print(f"DEBUG: setup_logger returning logger_instance: {logger_instance}")
    return logger_instance

def initialize_tweepy_client():
    global client
    global logger
    # print(f"DEBUG initialize_tweepy_client: global logger is currently: {logger}")
    if not logger:
        print("ERROR: Logger not initialized before Tweepy client attempt.")
        return False
    logger.info("Attempting to load .env file...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, '.env')
    logger.info(f"Expected .env path: {dotenv_path}")
    if not os.path.exists(dotenv_path):
        logger.error(f".env file NOT FOUND at: {dotenv_path}. Cannot load credentials.")
        return False
    else:
        logger.info(f".env file FOUND at: {dotenv_path}. Attempting to load.")
    loaded_successfully = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
    logger.info(f"load_dotenv() call returned: {loaded_successfully}")
    if not loaded_successfully:
        logger.warning(".env file was found but load_dotenv() reported not loading successfully (e.g. empty file).")
    API_KEY_val = os.getenv("API_KEY")
    API_SECRET_val = os.getenv("API_SECRET")
    ACCESS_TOKEN_val = os.getenv("ACCESS_TOKEN")
    ACCESS_TOKEN_SECRET_val = os.getenv("ACCESS_TOKEN_SECRET")
    logger.info(f"Attempting Tweepy Client init with .env loaded keys:")
    logger.info(f"  API_KEY from env: '{API_KEY_val}' (Type: {type(API_KEY_val)})")
    logger.info(f"  API_SECRET from env: '{API_SECRET_val}' (Type: {type(API_SECRET_val)})")
    logger.info(f"  ACCESS_TOKEN from env: '{ACCESS_TOKEN_val}' (Type: {type(ACCESS_TOKEN_val)})")
    logger.info(f"  ACCESS_TOKEN_SECRET from env: '{ACCESS_TOKEN_SECRET_val}' (Type: {type(ACCESS_TOKEN_SECRET_val)})")
    if not all([API_KEY_val, API_SECRET_val, ACCESS_TOKEN_val, ACCESS_TOKEN_SECRET_val]):
        logger.error(
            "One or more API credentials were not found after loading .env. "
            "Ensure API_KEY, API_SECRET, ACCESS_TOKEN, and ACCESS_TOKEN_SECRET are correctly defined in your .env file."
        )
        return False
    try:
        client = tweepy.Client(
            consumer_key=API_KEY_val,
            consumer_secret=API_SECRET_val,
            access_token=ACCESS_TOKEN_val,
            access_token_secret=ACCESS_TOKEN_SECRET_val,
            wait_on_rate_limit=True
        )
        user_response = client.get_me()
        if user_response.errors:
            logger.error(f"Twitter Authentication failed (after loading keys): {user_response.errors}")
            client = None
            return False
        if not user_response.data:
            logger.error(f"Twitter Authentication failed: get_me() returned no data. Errors: {user_response.errors}")
            client = None
            return False
        logger.info(f"Successfully authenticated with Twitter as @{user_response.data.username}")
        return True
    except Exception as e:
        logger.error(f"Exception during Twitter Authentication: {e}")
        client = None
        return False

def get_authenticated_user_id():
    global logger # Added global logger declaration
    if not client:
        if logger: logger.error("Tweepy client not initialized for get_authenticated_user_id.")
        else: print("ERROR: Logger and Tweepy client not initialized for get_authenticated_user_id.")
        return None
    try:
        user_response = client.get_me()
        if user_response.errors or not user_response.data:
            logger.error(f"Could not get authenticated user ID: {user_response.errors}")
            return None
        return user_response.data.id
    except Exception as e:
        logger.error(f"Exception getting user ID: {e}")
        return None

def delete_likes_in_range(user_id, start_dt_utc, end_dt_utc):
    global logger # Added global logger declaration
    logger.info("Starting to delete likes (based on TWEET CREATION date)...")
    deleted_count = 0
    if not client:
        logger.error("Client not available for deleting likes.")
        return
    try:
        for page in tweepy.Paginator(
            client.get_liked_tweets, user_id, max_results=100,
            tweet_fields=["created_at"]
        ):
            if page.errors:
                logger.error(f"Error in pagination for liked tweets: {page.errors}")
                break
            if not page.data:
                continue
            for liked_tweet_obj in page.data:
                if liked_tweet_obj.created_at and start_dt_utc <= liked_tweet_obj.created_at <= end_dt_utc:
                    try:
                        logger.info(f"Unliking tweet {liked_tweet_obj.id} (created at {liked_tweet_obj.created_at})")
                        client.unlike(liked_tweet_obj.id)
                        deleted_count += 1
                    except tweepy.TweepyException as e:
                        logger.error(f"Error unliking tweet {liked_tweet_obj.id}: {e}")
                elif liked_tweet_obj.created_at and liked_tweet_obj.created_at < start_dt_utc:
                    pass
        logger.info(f"Finished deleting likes. Total unliked: {deleted_count}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in delete_likes_in_range: {e}")

def delete_user_tweets_by_type(user_id, start_dt_utc, end_dt_utc, delete_replies_flag, delete_quotes_flag, delete_own_posts_flag):
    global logger # Added global logger declaration
    logger.info("Starting to delete user's tweets based on selection...")
    deleted_count = 0
    if not client:
        logger.error("Client not available for deleting user tweets.")
        return
    try:
        for page in tweepy.Paginator(
            client.get_users_tweets, user_id, max_results=100,
            tweet_fields=["created_at", "in_reply_to_user_id", "referenced_tweets"],
        ):
            if page.errors:
                logger.error(f"Error in pagination for user tweets: {page.errors}")
                break
            if not page.data:
                continue
            for tweet in page.data:
                if not (tweet.created_at and start_dt_utc <= tweet.created_at <= end_dt_utc):
                    if tweet.created_at and tweet.created_at < start_dt_utc:
                        pass
                    continue
                is_reply = bool(tweet.in_reply_to_user_id)
                is_quote = any(rt.type == 'quoted' for rt in tweet.referenced_tweets or [])
                action_taken = False
                try:
                    if delete_replies_flag and is_reply:
                        logger.info(f"Deleting reply {tweet.id} (created at {tweet.created_at})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                    elif delete_quotes_flag and is_quote and not action_taken:
                        logger.info(f"Deleting quote tweet {tweet.id} (created at {tweet.created_at})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                    elif delete_own_posts_flag and not is_reply and not is_quote and not action_taken:
                        logger.info(f"Deleting own post {tweet.id} (created at {tweet.created_at})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                except tweepy.TweepyException as e:
                    logger.error(f"Error deleting tweet {tweet.id} (type attempted: reply={is_reply}, quote={is_quote}, own={not is_reply and not is_quote}): {e}")
        logger.info(f"Finished deleting user tweets. Total deleted: {deleted_count}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in delete_user_tweets_by_type: {e}")

class TwitterDeleterApp:
    def __init__(self, root_window):
        self.root = root_window
        root_window.title("Twitter Content Deleter")
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            # Logger might not be initialized here yet, so use print as a fallback
            print("WARNING: Clam theme not available, using default (logger not yet init).")
        main_frame = ttk.Frame(root_window, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root_window.columnconfigure(0, weight=1)
        root_window.rowconfigure(0, weight=1)
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.start_date_entry = ttk.Entry(main_frame, width=15)
        self.start_date_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        self.start_date_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.end_date_entry = ttk.Entry(main_frame, width=15)
        self.end_date_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        ttk.Label(main_frame, text="Select actions to perform:").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10,2))
        self.delete_likes_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Delete Likes", variable=self.delete_likes_var).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        self.delete_replies_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Delete My Replies", variable=self.delete_replies_var).grid(row=4, column=0, columnspan=2, sticky=tk.W)
        self.delete_own_posts_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Delete My Own Original Posts", variable=self.delete_own_posts_var).grid(row=5, column=0, columnspan=2, sticky=tk.W)
        self.delete_quotes_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Delete My Quoted Posts", variable=self.delete_quotes_var).grid(row=6, column=0, columnspan=2, sticky=tk.W)
        self.start_button = ttk.Button(main_frame, text="Start Deletion", command=self.start_deletion_thread)
        self.start_button.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Label(main_frame, text="Log:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.log_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15, width=70, state='disabled')
        self.log_text.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(9, weight=1)

        global logger # Declare that we intend to modify the global logger
        logger = setup_logger(self.log_text)
        # print(f"DEBUG App.__init__: global logger after setup is: {logger}")

        if not initialize_tweepy_client():
            messagebox.showerror("Authentication Error", "Failed to authenticate with Twitter. Check logs and .env file.")
        else:
            if logger: logger.info("GUI Initialized. Twitter client ready.")
            else: print("INFO: GUI Initialized. Twitter client ready. (Logger was None during this message).")


    def validate_dates(self):
        try:
            start_str = self.start_date_entry.get()
            end_str = self.end_date_entry.get()
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            start_dt_utc = start_dt.replace(tzinfo=timezone.utc)
            end_dt_utc = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            if start_dt_utc > end_dt_utc:
                messagebox.showerror("Date Error", "Start date must be before or equal to end date.")
                return None, None
            return start_dt_utc, end_dt_utc
        except ValueError:
            messagebox.showerror("Date Error", "Dates must be in YYYY-MM-DD format.")
            return None, None

    def start_deletion_thread(self):
        self.start_button.config(state=tk.DISABLED)
        thread = threading.Thread(target=self.process_deletions, daemon=True)
        thread.start()

    def process_deletions(self):
        global client
        global logger # Declare that we intend to use the global logger
        if not client:
            if logger: logger.error("Twitter client not initialized. Cannot proceed with deletions.")
            else: print("ERROR: Twitter client not initialized (process_deletions)")
            messagebox.showerror("Error", "Twitter client not initialized. Check authentication logs.")
            self.start_button.config(state=tk.NORMAL)
            return
        start_dt_utc, end_dt_utc = self.validate_dates()
        if not start_dt_utc:
            self.start_button.config(state=tk.NORMAL)
            return
        actions_selected = (self.delete_likes_var.get() or
                            self.delete_replies_var.get() or
                            self.delete_own_posts_var.get() or
                            self.delete_quotes_var.get())
        if not actions_selected:
            messagebox.showwarning("No Action", "Please select at least one action to perform.")
            self.start_button.config(state=tk.NORMAL)
            return
        confirm_msg = (f"Are you sure you want to delete selected content from "
                       f"{start_dt_utc.strftime('%Y-%m-%d')} to {end_dt_utc.strftime('%Y-%m-%d')}?\n"
                       "This action is IRREVERSIBLE.")
        if not messagebox.askyesno("Confirm Deletion", confirm_msg):
            if logger: logger.info("Deletion cancelled by user.")
            else: print("INFO: Deletion cancelled by user.")
            self.start_button.config(state=tk.NORMAL)
            return
        if logger: logger.info("Starting deletion process in background thread...")
        else: print("INFO: Starting deletion process in background thread...")

        user_id = get_authenticated_user_id()
        if not user_id:
            if logger: logger.error("Failed to get user ID for deletion tasks. Aborting.")
            else: print("ERROR: Failed to get user ID for deletion tasks. Aborting.")
            self.start_button.config(state=tk.NORMAL)
            return
        if self.delete_likes_var.get():
            delete_likes_in_range(user_id, start_dt_utc, end_dt_utc)
        if self.delete_replies_var.get() or self.delete_own_posts_var.get() or self.delete_quotes_var.get():
            delete_user_tweets_by_type(user_id, start_dt_utc, end_dt_utc,
                                       self.delete_replies_var.get(),
                                       self.delete_quotes_var.get(),
                                       self.delete_own_posts_var.get())
        if logger: logger.info("All selected deletion tasks processing initiated.")
        else: print("INFO: All selected deletion tasks processing initiated.")
        messagebox.showinfo("Processing", "Deletion tasks started. Check logs for progress and completion.")
        self.start_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = TwitterDeleterApp(root)
    root.mainloop()
