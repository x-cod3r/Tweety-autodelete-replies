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
    if not logger_instance.hasHandlers():
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger_instance.addHandler(ch)
        
        gui_handler = GuiHandler(log_text_widget)
        gui_handler.setFormatter(formatter)
        logger_instance.addHandler(gui_handler)
    return logger_instance

def initialize_tweepy_client():
    global client
    global logger
    if not logger:
        print("CRITICAL ERROR: Logger not initialized before Tweepy client initialization attempt.")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        logger = logging.getLogger("TwitterDeleterGUI_Fallback")
        logger.error("Fallback logger activated. GUI logger was not available.")

    logger.info("Attempting to load .env file...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, '.env')
    logger.info(f"Expected .env path: {dotenv_path}")

    if not os.path.exists(dotenv_path):
        logger.error(f".env file NOT FOUND at: {dotenv_path}. Cannot load credentials.")
        messagebox.showerror("Environment Error", f".env file not found at {dotenv_path}. Please create it with your API credentials.")
        return False
    else:
        logger.info(f".env file FOUND at: {dotenv_path}. Attempting to load.")
    
    loaded_successfully = load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
    logger.info(f"load_dotenv() call returned: {loaded_successfully}")

    if not loaded_successfully:
        logger.warning(".env file was found but load_dotenv() reported not loading successfully (e.g. empty file or issue parsing).")

    API_KEY_val = os.getenv("API_KEY")
    API_SECRET_val = os.getenv("API_SECRET")
    ACCESS_TOKEN_val = os.getenv("ACCESS_TOKEN")
    ACCESS_TOKEN_SECRET_val = os.getenv("ACCESS_TOKEN_SECRET")

    logger.info(f"Attempting Tweepy Client init with .env loaded keys:")
    logger.info(f"  API_KEY from env: '{'SET' if API_KEY_val else 'NOT SET'}'")
    logger.info(f"  API_SECRET from env: '{'SET' if API_SECRET_val else 'NOT SET'}'")
    logger.info(f"  ACCESS_TOKEN from env: '{'SET' if ACCESS_TOKEN_val else 'NOT SET'}'")
    logger.info(f"  ACCESS_TOKEN_SECRET from env: '{'SET' if ACCESS_TOKEN_SECRET_val else 'NOT SET'}'")

    if not all([API_KEY_val, API_SECRET_val, ACCESS_TOKEN_val, ACCESS_TOKEN_SECRET_val]):
        logger.error(
            "One or more API credentials were not found after loading .env. "
            "Ensure API_KEY, API_SECRET, ACCESS_TOKEN, and ACCESS_TOKEN_SECRET are correctly defined in your .env file."
        )
        messagebox.showerror("Credentials Error", "One or more API credentials missing from .env file. Check logs.")
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
            for error in user_response.errors:
                logger.error(f"Error detail: {error.get('title', 'Unknown error')}: {error.get('detail', 'No details')}")
            client = None
            return False
        if not user_response.data:
            logger.error(f"Twitter Authentication failed: get_me() returned no data. Errors: {user_response.errors}")
            client = None
            return False
        logger.info(f"Successfully authenticated with Twitter as @{user_response.data.username} (ID: {user_response.data.id})")
        return True
    except tweepy.TweepyException as e:
        logger.error(f"TweepyException during Twitter Authentication: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Twitter API response status: {e.response.status_code}")
            logger.error(f"Twitter API response text: {e.response.text}")
        client = None
        return False
    except Exception as e:
        logger.error(f"Unexpected exception during Twitter Authentication: {e}", exc_info=True)
        client = None
        return False

def get_authenticated_user_id():
    global logger 
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
    except tweepy.TweepyException as e:
        logger.error(f"TweepyException getting user ID: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Twitter API response status: {e.response.status_code}")
            logger.error(f"Twitter API response text: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Exception getting user ID: {e}", exc_info=True)
        return None

def log_tweepy_error(e, context_message=""):
    global logger
    logger.error(f"{context_message}: {e}")
    if hasattr(e, 'response') and e.response is not None:
        logger.error(f"Twitter API response status: {e.response.status_code}")
        logger.error(f"Twitter API response text: {e.response.text}")
        if e.response.status_code in [401, 403]:
            logger.error(
                "A 401 (Unauthorized) or 403 (Forbidden) error occurred. "
                "This usually means the Access Tokens used do not have 'Write' permissions. "
                "Please check your Twitter Developer App settings: "
                "1. Ensure 'App permissions' are set to 'Read and Write'. "
                "2. **Regenerate** your Access Token and Secret after confirming/changing permissions. "
                "3. Update your .env file with the new tokens."
            )
    elif hasattr(e, 'api_errors') and e.api_errors:
        logger.error(f"API Errors: {e.api_errors}")
    elif hasattr(e, 'reason') and e.reason:
        logger.error(f"Reason: {e.reason}")

def delete_likes_in_range(user_id, start_dt_utc, end_dt_utc):
    global logger
    logger.info("Starting to delete likes (based on TWEET CREATION date)...")
    deleted_count = 0
    processed_count = 0
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
                for error in page.errors:
                    logger.error(f"  Error detail: {error}")
                break 
            if not page.data:
                logger.info("No liked tweets found in this page or at all.")
                break
            
            for liked_tweet_obj in page.data:
                processed_count += 1
                if liked_tweet_obj.created_at:
                    tweet_created_at_utc = liked_tweet_obj.created_at.replace(tzinfo=timezone.utc)
                    if start_dt_utc <= tweet_created_at_utc <= end_dt_utc:
                        try:
                            logger.info(f"Unliking tweet {liked_tweet_obj.id} (created at {tweet_created_at_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                            client.unlike(liked_tweet_obj.id)
                            deleted_count += 1
                        except tweepy.TweepyException as e:
                            log_tweepy_error(e, f"Error unliking tweet {liked_tweet_obj.id}")
                    elif tweet_created_at_utc < start_dt_utc:
                        pass 
                else:
                    logger.warning(f"Tweet {liked_tweet_obj.id} has no creation date. Skipping.")
            
            logger.info(f"Processed page of liked tweets. Total processed so far: {processed_count}, total unliked in range: {deleted_count}")

        logger.info(f"Finished deleting likes. Total unliked: {deleted_count} out of {processed_count} liked tweets considered.")
    except tweepy.TweepyException as e:
        log_tweepy_error(e, "A TweepyException occurred in delete_likes_in_range main loop")
    except Exception as e:
        logger.error(f"An unexpected error occurred in delete_likes_in_range: {e}", exc_info=True)

def delete_user_tweets_by_type(user_id, start_dt_utc, end_dt_utc, delete_replies_flag, delete_quotes_flag, delete_own_posts_flag):
    global logger
    logger.info("Starting to delete user's tweets based on selection...")
    deleted_count = 0
    processed_count = 0
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
                for error in page.errors:
                     logger.error(f"  Error detail: {error}")
                break
            if not page.data:
                logger.info("No tweets found in this page or for the user.")
                break

            for tweet in page.data:
                processed_count +=1
                if not tweet.created_at:
                    logger.warning(f"Tweet {tweet.id} has no creation date. Skipping.")
                    continue
                
                tweet_created_at_utc = tweet.created_at.replace(tzinfo=timezone.utc)

                if not (start_dt_utc <= tweet_created_at_utc <= end_dt_utc):
                    if tweet_created_at_utc < start_dt_utc:
                        logger.info(f"Tweet {tweet.id} (at {tweet_created_at_utc}) is older than start date {start_dt_utc}. Assuming no more relevant tweets.")
                        logger.info(f"Finished deleting user tweets. Total deleted: {deleted_count} out of {processed_count} tweets considered.")
                        return
                    continue

                is_reply = bool(tweet.in_reply_to_user_id)
                is_quote = any(rt.type == 'quoted' for rt in tweet.referenced_tweets or [])
                is_retweet = any(rt.type == 'retweeted' for rt in tweet.referenced_tweets or [])

                if is_retweet:
                    logger.info(f"Skipping retweet {tweet.id} (created at {tweet_created_at_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                    continue

                action_taken = False
                try:
                    if delete_replies_flag and is_reply:
                        logger.info(f"Deleting reply {tweet.id} (created at {tweet_created_at_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                    elif delete_quotes_flag and is_quote and not action_taken:
                        logger.info(f"Deleting quote tweet {tweet.id} (created at {tweet_created_at_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                    elif delete_own_posts_flag and not is_reply and not is_quote and not action_taken:
                        logger.info(f"Deleting own post {tweet.id} (created at {tweet_created_at_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                        client.delete_tweet(tweet.id)
                        deleted_count += 1
                        action_taken = True
                except tweepy.TweepyException as e:
                    log_tweepy_error(e, f"Error deleting tweet {tweet.id} (type attempted: reply={is_reply}, quote={is_quote}, own={not is_reply and not is_quote})")
            
            logger.info(f"Processed page of user tweets. Total processed so far: {processed_count}, total deleted in range: {deleted_count}")

        logger.info(f"Finished deleting user tweets. Total deleted: {deleted_count} out of {processed_count} tweets considered.")
    except tweepy.TweepyException as e:
        log_tweepy_error(e, "A TweepyException occurred in delete_user_tweets_by_type main loop")
    except Exception as e:
        logger.error(f"An unexpected error occurred in delete_user_tweets_by_type: {e}", exc_info=True)

class TwitterDeleterApp:
    def __init__(self, root_window):
        self.root = root_window
        root_window.title("Twitter Content Deleter")
        style = ttk.Style()
        try:
            if 'clam' in style.theme_names():
                style.theme_use('clam')
            elif 'vista' in style.theme_names():
                 style.theme_use('vista')
            elif 'aqua' in style.theme_names():
                 style.theme_use('aqua')
        except tk.TclError:
            print("WARNING: Chosen ttk theme not available, using default.")
        
        main_frame = ttk.Frame(root_window, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root_window.columnconfigure(0, weight=1)
        root_window.rowconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5 5 5 5")
        log_frame.grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10,0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, width=70, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        global logger 
        logger = setup_logger(self.log_text)

        if not initialize_tweepy_client():
            logger.warning("GUI initialized, but Twitter client failed to initialize. Functionality will be limited.")
        else:
            logger.info("GUI Initialized. Twitter client ready.")

        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5 5 5 5")
        controls_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5) # Corrected sticky value
        controls_frame.columnconfigure(1, weight=1)

        ttk.Label(controls_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=2)
        self.start_date_entry = ttk.Entry(controls_frame, width=15)
        self.start_date_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=2)
        self.start_date_entry.insert(0, (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d"))

        ttk.Label(controls_frame, text="End Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=2, padx=2)
        self.end_date_entry = ttk.Entry(controls_frame, width=15)
        self.end_date_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=2)
        self.end_date_entry.insert(0, datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        ttk.Label(controls_frame, text="Select actions to perform:").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10,2), padx=2)
        
        self.delete_likes_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Delete Likes (tweeted within date range)", variable=self.delete_likes_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        self.delete_replies_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Delete My Replies", variable=self.delete_replies_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        self.delete_own_posts_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Delete My Own Original Posts (not replies, not quotes)", variable=self.delete_own_posts_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        self.delete_quotes_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Delete My Quoted Posts", variable=self.delete_quotes_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=5)
        
        self.start_button = ttk.Button(controls_frame, text="Start Deletion", command=self.start_deletion_thread)
        self.start_button.grid(row=7, column=0, columnspan=2, pady=10, padx=2)

        main_frame.rowconfigure(10, weight=1)

    def validate_dates(self):
        global logger
        try:
            start_str = self.start_date_entry.get()
            end_str = self.end_date_entry.get()
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            
            start_dt_utc = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, tzinfo=timezone.utc)
            end_dt_utc = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

            if start_dt_utc > end_dt_utc:
                logger.error("Date validation error: Start date must be before or equal to end date.")
                messagebox.showerror("Date Error", "Start date must be before or equal to end date.")
                return None, None
            logger.info(f"Date range validated: {start_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} to {end_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return start_dt_utc, end_dt_utc
        except ValueError:
            logger.error("Date validation error: Dates must be in YYYY-MM-DD format.")
            messagebox.showerror("Date Error", "Dates must be in YYYY-MM-DD format.")
            return None, None

    def start_deletion_thread(self):
        global logger
        if not client:
             logger.error("Cannot start deletion: Twitter client not initialized.")
             messagebox.showerror("Error", "Twitter client not initialized. Please check credentials and logs, then restart.")
             return

        self.start_button.config(state=tk.DISABLED)
        logger.info("Start deletion button clicked, initiating deletion thread.")
        thread = threading.Thread(target=self.process_deletions, daemon=True)
        thread.start()

    def process_deletions(self):
        global client
        global logger 
        
        start_dt_utc, end_dt_utc = self.validate_dates()
        if not start_dt_utc or not end_dt_utc :
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            return

        actions_selected = (self.delete_likes_var.get() or
                            self.delete_replies_var.get() or
                            self.delete_own_posts_var.get() or
                            self.delete_quotes_var.get())
        if not actions_selected:
            logger.warning("No action selected by the user.")
            messagebox.showwarning("No Action", "Please select at least one action to perform.")
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            return

        confirm_msg = (f"Are you sure you want to delete selected content from "
                       f"{start_dt_utc.strftime('%Y-%m-%d')} to {end_dt_utc.strftime('%Y-%m-%d')}?\n"
                       "This action is IRREVERSIBLE.")
        
        if not messagebox.askyesno("Confirm Deletion", confirm_msg, master=self.root):
            logger.info("Deletion cancelled by user.")
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            return
        
        logger.info("User confirmed. Starting deletion process...")

        user_id = get_authenticated_user_id()
        if not user_id:
            logger.error("Failed to get user ID for deletion tasks. Aborting.")
            messagebox.showerror("Error", "Could not retrieve your user ID. Check authentication and logs.", master=self.root)
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            return
        
        logger.info(f"Operating for user ID: {user_id}")

        if self.delete_likes_var.get():
            delete_likes_in_range(user_id, start_dt_utc, end_dt_utc)
        
        if self.delete_replies_var.get() or self.delete_own_posts_var.get() or self.delete_quotes_var.get():
            delete_user_tweets_by_type(user_id, start_dt_utc, end_dt_utc,
                                       self.delete_replies_var.get(),
                                       self.delete_quotes_var.get(),
                                       self.delete_own_posts_var.get())
        
        logger.info("All selected deletion tasks processing initiated/completed.")
        self.root.after(0, lambda: messagebox.showinfo("Processing Complete", "Deletion tasks have finished. Check logs for details.", master=self.root))
        self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))


if __name__ == "__main__":
    root = tk.Tk()
    app = TwitterDeleterApp(root)
    root.mainloop()
