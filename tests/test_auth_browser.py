import io
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from myfap import auth as module
from myfap.oidc import OIDCClient, OAuthError


PRIVATE_SENTINEL = "PRIVATE_BROWSER_SENTINEL"


class AuthBrowserTests(unittest.TestCase):
    def setUp(self):
        self.auth = module.MyFapAuth()
        self.oidc = OIDCClient(
            Mock(), issuer="https://identity.example.invalid", client_id="test-cli",
            redirect_uri="io.example.cli:/callback",
        )
        self.oidc.parse_callback = Mock(wraps=self.oidc.parse_callback)
        self.attempt = {"url": "https://identity.example.invalid/authorize", "state": "test-state"}
        self.callback = "io.example.cli:/callback?state=test-state&code=fake-code"
        self.handlers = {}
        self.page = Mock()
        self.page.on.side_effect = lambda event, handler: self.handlers.__setitem__(event, handler)
        self.browser = Mock()
        self.browser.new_context.return_value.new_page.return_value = self.page
        playwright = SimpleNamespace(chromium=Mock(), firefox=Mock())
        playwright.chromium.launch.return_value = self.browser
        playwright.firefox.launch.return_value = self.browser
        manager = MagicMock()
        manager.__enter__.return_value = playwright
        self.playwright_patch = patch.object(module, "sync_playwright", return_value=manager)
        self.playwright_patch.start()
        self.addCleanup(self.playwright_patch.stop)
        self.stderr = io.StringIO()

    def authorize(self, times=(0, 1)):
        with patch.object(module.time, "monotonic", side_effect=times), redirect_stderr(self.stderr):
            return self.auth._authorize(self.oidc, self.attempt)

    def emit_request(self, url):
        self.handlers["request"](SimpleNamespace(url=url))

    def emit_response(self, url):
        self.handlers["response"](SimpleNamespace(status=302, headers={"location": url}))

    def assert_safe_failure(self, exception):
        self.assertNotIn(PRIVATE_SENTINEL, str(exception))
        self.assertNotIn(PRIVATE_SENTINEL, self.stderr.getvalue())
        self.browser.close.assert_called_once_with()

    def test_duplicate_request_and_response_callback_is_consumed_once(self):
        def navigate(_):
            self.emit_request(self.callback)
            self.emit_response(self.callback)
            self.emit_request(self.callback)

        self.page.goto.side_effect = navigate
        self.assertEqual(self.authorize(), "fake-code")
        self.oidc.parse_callback.assert_called_once_with(self.callback, self.attempt)
        self.page.wait_for_timeout.assert_not_called()
        self.browser.close.assert_called_once_with()

    def test_response_callback_can_complete_after_unrelated_request(self):
        def navigate(_):
            self.emit_request("https://identity.example.invalid/sign-in")
            self.emit_response(self.callback)
            self.emit_request(self.callback)

        self.page.goto.side_effect = navigate
        self.assertEqual(self.authorize(), "fake-code")
        self.assertEqual(self.oidc.parse_callback.call_count, 2)
        self.browser.close.assert_called_once_with()

    def test_oauth_cancellation_is_safe_and_later_callback_is_ignored(self):
        def navigate(_):
            self.emit_response(f"io.example.cli:/callback?state=test-state&error=access_denied&error_description={PRIVATE_SENTINEL}")
            self.emit_request(self.callback)

        self.page.goto.side_effect = navigate
        with self.assertRaises(OAuthError) as caught:
            self.authorize()
        self.assertEqual(caught.exception.code, "access_denied")
        self.assertEqual(self.oidc.parse_callback.call_count, 1)
        self.assert_safe_failure(caught.exception)

    def test_invalid_oauth_callback_preserves_safe_error(self):
        self.page.goto.side_effect = lambda _: self.emit_request(f"io.example.cli:/callback?state={PRIVATE_SENTINEL}&code=fake-code")
        with self.assertRaises(OAuthError) as caught:
            self.authorize()
        self.assertEqual(caught.exception.code, "callback")
        self.assert_safe_failure(caught.exception)

    def test_120_second_deadline_closes_browser_without_polling_after_expiry(self):
        with self.assertRaisesRegex(module.AuthError, "thời gian chờ") as caught:
            self.authorize(times=(10, 129, 130))
        self.page.wait_for_timeout.assert_called_once_with(250)
        self.assert_safe_failure(caught.exception)

    def test_closed_browser_raises_safe_error(self):
        self.page.wait_for_timeout.side_effect = RuntimeError(PRIVATE_SENTINEL)
        with self.assertRaisesRegex(module.AuthError, "đã đóng") as caught:
            self.authorize()
        self.assert_safe_failure(caught.exception)

    def test_keyboard_interrupt_is_safe_during_navigation_or_wait(self):
        for stage in ("goto", "wait_for_timeout"):
            with self.subTest(stage=stage):
                self.browser.close.reset_mock()
                self.page.goto.side_effect = None
                self.page.wait_for_timeout.side_effect = None
                getattr(self.page, stage).side_effect = KeyboardInterrupt(PRIVATE_SENTINEL)
                with self.assertRaisesRegex(module.AuthError, "hủy") as caught:
                    self.authorize()
                self.assert_safe_failure(caught.exception)

    def test_browser_setup_exception_is_safe_and_closes_browser(self):
        self.browser.new_context.side_effect = RuntimeError(PRIVATE_SENTINEL)
        with self.assertRaises(module.AuthError) as caught:
            self.authorize()
        self.assert_safe_failure(caught.exception)

    def test_cleanup_error_does_not_override_success_or_safe_failure(self):
        for succeeds in (True, False):
            with self.subTest(succeeds=succeeds):
                self.browser.close.reset_mock()
                self.browser.close.side_effect = RuntimeError(PRIVATE_SENTINEL)
                self.page.goto.side_effect = (lambda _: self.emit_request(self.callback)) if succeeds else None
                self.page.wait_for_timeout.side_effect = RuntimeError(PRIVATE_SENTINEL)
                if succeeds:
                    self.assertEqual(self.authorize(), "fake-code")
                    self.browser.close.assert_called_once_with()
                else:
                    with self.assertRaises(module.AuthError) as caught:
                        self.authorize()
                    self.assert_safe_failure(caught.exception)


if __name__ == "__main__":
    unittest.main()
