# actions/app_builder/codegen.py
# ══════════════════════════════════════════════════════════════
# JARVIS Flutter App Builder — Dart Code Generator
# Generates pubspec.yaml, main.dart, theme, router,
# all screens, models, providers, services
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import re
from .brain import AppPlan
from core.ai_router import get_ai_router


class FlutterCodeGen:
    """Generates all Dart/Flutter files for the project."""

    def __init__(self):
        self.router = get_ai_router()

    def _call(self, prompt: str) -> str:
        return self.router.generate(prompt)

    def _extract(self, text: str, lang: str = "dart") -> str:
        pattern = rf"```(?:{lang})?\s*(.*?)```"
        match   = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Remove any remaining fences
        text = re.sub(r"```\w*\n?", "", text).strip()
        return text

    # ─────────────────────────────────────────────────────────
    # pubspec.yaml
    # ─────────────────────────────────────────────────────────
    def gen_pubspec(self, plan: AppPlan) -> str:
        packages = plan.get_packages()
        pkg_lines = "\n".join(f"  {p}: ^latest" for p in packages)
        # Handle special versioning
        pkg_lines = pkg_lines.replace(
            "  flutter_riverpod: ^latest", "  flutter_riverpod: ^2.5.1")
        pkg_lines = pkg_lines.replace(
            "  go_router: ^latest", "  go_router: ^14.2.7")
        pkg_lines = pkg_lines.replace(
            "  dio: ^latest", "  dio: ^5.7.0")

        return f"""name: {re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())}
description: "{plan.app_description[:120]}"
version: 1.0.0+1
publish_to: 'none'

environment:
  sdk: '>=3.4.0 <4.0.0'
  flutter: ">=3.22.0"

dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
{pkg_lines}
  google_fonts: ^6.2.1

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^4.0.0
  build_runner: ^2.4.13
  json_serializable: ^6.8.0
  riverpod_generator: ^2.4.3

flutter:
  uses-material-design: true
  assets:
    - assets/images/
    - assets/animations/
    - assets/icons/
  fonts:
    - family: {plan.font_family}
      fonts:
        - asset: assets/fonts/{plan.font_family}-Regular.ttf
          weight: 400
        - asset: assets/fonts/{plan.font_family}-Medium.ttf
          weight: 500
        - asset: assets/fonts/{plan.font_family}-SemiBold.ttf
          weight: 600
        - asset: assets/fonts/{plan.font_family}-Bold.ttf
          weight: 700
"""

    # ─────────────────────────────────────────────────────────
    # main.dart
    # ─────────────────────────────────────────────────────────
    def gen_main_dart(self, plan: AppPlan) -> str:
        app_name_var = re.sub(r'[^a-zA-Z0-9]', '', plan.app_name) + "App"
        riverpod_wrap = (
            "ProviderScope(\n      child: " if plan.state_mgmt == "riverpod"
            else ""
        )
        riverpod_close = ("\n      ),\n    )" if plan.state_mgmt == "riverpod" else "")
        firebase_init  = (
            "await Firebase.initializeApp(\n"
            "        options: DefaultFirebaseOptions.currentPlatform,\n"
            "      );\n"
            if plan.use_firebase else ""
        )
        firebase_import = (
            "import 'package:firebase_core/firebase_core.dart';\n"
            "import 'firebase_options.dart';\n"
            if plan.use_firebase else ""
        )

        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())

        return f"""import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
{firebase_import}import 'package:{pkg}/core/theme/app_theme.dart';
import 'package:{pkg}/core/router/app_router.dart';
{f"import 'package:flutter_riverpod/flutter_riverpod.dart';" if plan.state_mgmt == "riverpod" else "import 'package:provider/provider.dart';"}

void main() async {{
  WidgetsFlutterBinding.ensureInitialized();
  {firebase_init}
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  runApp(
    {riverpod_wrap}const {app_name_var}(){riverpod_close}
  );
}}

class {app_name_var} extends StatelessWidget {{
  const {app_name_var}({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp.router(
      title: '{plan.app_name}',
      debugShowCheckedModeBanner: false,
      theme:      AppTheme.lightTheme,
      darkTheme:  AppTheme.darkTheme,
      themeMode:  ThemeMode.{'dark' if plan.color_theme == 'dark' else 'system'},
      routerConfig: AppRouter.router,
    );
  }}
}}
"""

    # ─────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────
    def gen_theme(self, plan: AppPlan) -> str:
        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())
        return f"""import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppColors {{
  // Primary palette
  static const primary     = Color({plan.primary_color});
  static const accent      = Color({plan.accent_color});
  static const primaryDark = Color(0xFF4F46E5);

  // Dark theme
  static const darkBg       = Color(0xFF0A0A0F);
  static const darkSurface  = Color(0xFF111118);
  static const darkCard     = Color(0xFF1A1A24);
  static const darkBorder   = Color(0xFF2A2A3A);

  // Light theme
  static const lightBg      = Color(0xFFF8FAFF);
  static const lightSurface = Color(0xFFFFFFFF);
  static const lightCard    = Color(0xFFF1F5FF);
  static const lightBorder  = Color(0xFFE4E8FF);

  // Text
  static const textPrimary   = Color(0xFFF1F5F9);
  static const textSecondary = Color(0xFF94A3B8);
  static const textMuted     = Color(0xFF64748B);

  // Status
  static const success = Color(0xFF10B981);
  static const warning = Color(0xFFF59E0B);
  static const error   = Color(0xFFEF4444);
  static const info    = Color(0xFF3B82F6);
}}

class AppTheme {{
  static TextTheme _textTheme(Color primary, Color secondary) {{
    return TextTheme(
      displayLarge:  GoogleFonts.{plan.font_family.lower()}(
        fontSize: 57, fontWeight: FontWeight.w700, color: primary),
      displayMedium: GoogleFonts.{plan.font_family.lower()}(
        fontSize: 45, fontWeight: FontWeight.w700, color: primary),
      displaySmall:  GoogleFonts.{plan.font_family.lower()}(
        fontSize: 36, fontWeight: FontWeight.w600, color: primary),
      headlineLarge: GoogleFonts.{plan.font_family.lower()}(
        fontSize: 32, fontWeight: FontWeight.w700, color: primary),
      headlineMedium:GoogleFonts.{plan.font_family.lower()}(
        fontSize: 28, fontWeight: FontWeight.w600, color: primary),
      headlineSmall: GoogleFonts.{plan.font_family.lower()}(
        fontSize: 24, fontWeight: FontWeight.w600, color: primary),
      titleLarge:    GoogleFonts.{plan.font_family.lower()}(
        fontSize: 22, fontWeight: FontWeight.w600, color: primary),
      titleMedium:   GoogleFonts.{plan.font_family.lower()}(
        fontSize: 16, fontWeight: FontWeight.w500, color: primary),
      titleSmall:    GoogleFonts.{plan.font_family.lower()}(
        fontSize: 14, fontWeight: FontWeight.w500, color: secondary),
      bodyLarge:     GoogleFonts.{plan.font_family.lower()}(
        fontSize: 16, fontWeight: FontWeight.w400, color: primary),
      bodyMedium:    GoogleFonts.{plan.font_family.lower()}(
        fontSize: 14, fontWeight: FontWeight.w400, color: secondary),
      bodySmall:     GoogleFonts.{plan.font_family.lower()}(
        fontSize: 12, fontWeight: FontWeight.w400, color: secondary),
      labelLarge:    GoogleFonts.{plan.font_family.lower()}(
        fontSize: 14, fontWeight: FontWeight.w600, color: primary),
    );
  }}

  static ThemeData get darkTheme => ThemeData(
    useMaterial3: true,
    brightness:   Brightness.dark,
    colorScheme:  ColorScheme.dark(
      primary:     AppColors.primary,
      secondary:   AppColors.accent,
      surface:     AppColors.darkSurface,
      background:  AppColors.darkBg,
      error:       AppColors.error,
      onPrimary:   Colors.white,
      onSecondary: Colors.white,
      onSurface:   AppColors.textPrimary,
      onBackground:AppColors.textPrimary,
    ),
    scaffoldBackgroundColor: AppColors.darkBg,
    textTheme: _textTheme(AppColors.textPrimary, AppColors.textSecondary),
    appBarTheme: const AppBarTheme(
      backgroundColor:  AppColors.darkSurface,
      foregroundColor:  AppColors.textPrimary,
      elevation:        0,
      centerTitle:      true,
      titleTextStyle:   TextStyle(
        color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w600),
    ),
    cardTheme: CardTheme(
      color:        AppColors.darkCard,
      elevation:    0,
      shape:        RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.darkBorder, width: 1),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        minimumSize:     const Size(double.infinity, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 0,
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled:      true,
      fillColor:   AppColors.darkCard,
      border:      OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.darkBorder),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.darkBorder),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.primary, width: 2),
      ),
      hintStyle: const TextStyle(color: AppColors.textMuted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor:        AppColors.darkSurface,
      indicatorColor:         AppColors.primary.withOpacity(0.2),
      iconTheme: MaterialStateProperty.resolveWith((states) {{
        if (states.contains(MaterialState.selected))
          return const IconThemeData(color: AppColors.primary);
        return const IconThemeData(color: AppColors.textSecondary);
      }}),
      labelTextStyle: MaterialStateProperty.resolveWith((states) {{
        if (states.contains(MaterialState.selected))
          return const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w600, fontSize: 12);
        return const TextStyle(color: AppColors.textSecondary, fontSize: 12);
      }}),
      elevation: 0,
      height:    64,
    ),
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor:    AppColors.darkSurface,
      selectedItemColor:  AppColors.primary,
      unselectedItemColor:AppColors.textSecondary,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
    ),
  );

  static ThemeData get lightTheme => ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: ColorScheme.light(
      primary:    AppColors.primary,
      secondary:  AppColors.accent,
      surface:    AppColors.lightSurface,
      background: AppColors.lightBg,
      error:      AppColors.error,
    ),
    scaffoldBackgroundColor: AppColors.lightBg,
    textTheme: _textTheme(const Color(0xFF0F172A), const Color(0xFF475569)),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.lightSurface,
      foregroundColor: Color(0xFF0F172A),
      elevation: 0, centerTitle: true,
    ),
  );
}}
"""

    # ─────────────────────────────────────────────────────────
    # Router (GoRouter)
    # ─────────────────────────────────────────────────────────
    def gen_router(self, plan: AppPlan) -> str:
        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())

        # Build route list
        routes = []
        for screen in plan.screens:
            class_name = ''.join(w.title() for w in screen.split('_')) + 'Screen'
            path = f'/{screen.replace("_", "-")}'
            if screen == "splash":
                path = "/"
            routes.append((path, screen, class_name))

        imports = "\n".join(
            f"import 'package:{pkg}/features/{s}/presentation/screens/{s}_screen.dart';"
            for _, s, _ in routes
        )

        go_routes = "\n".join(
            f"""      GoRoute(
        path:     '{p}',
        name:     '{s}',
        builder:  (ctx, state) => const {c}(),
      ),"""
            for p, s, c in routes
        )

        first_route = routes[0][0] if routes else "/"
        initial    = "/" if plan.has_auth else routes[0][0] if routes else "/"

        return f"""import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
{imports}

class AppRouter {{
  static final router = GoRouter(
    initialLocation: '{initial}',
    debugLogDiagnostics: false,
    routes: [
{go_routes}
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text('Page not found: ${{state.uri}}',
                style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.go('/'),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );

  // Navigation helpers
  static void go(BuildContext context, String name, {{Object? extra}}) =>
      context.goNamed(name, extra: extra);

  static void push(BuildContext context, String name, {{Object? extra}}) =>
      context.pushNamed(name, extra: extra);

  static void pop(BuildContext context) => context.pop();
}}

// Route names as constants
class Routes {{
{chr(10).join(f"  static const {s} = '{s}';" for _, s, _ in routes)}
}}
"""

    # ─────────────────────────────────────────────────────────
    # Screen generator
    # ─────────────────────────────────────────────────────────
    def gen_screen(self, screen_name: str, plan: AppPlan) -> str:
        class_name = ''.join(w.title() for w in screen_name.split('_')) + 'Screen'
        pkg        = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())

        prompt = f"""Write a complete, production-quality Flutter screen.

App: {plan.app_name} ({plan.app_type})
Screen: {screen_name} → class: {class_name}
Description: {plan.app_description}
Architecture: {plan.arch_key} ({plan.pattern})
State mgmt: {plan.state_mgmt}
Theme: {plan.color_theme}
Primary color: Color({plan.primary_color})
Accent color: Color({plan.accent_color})
Font: {plan.font_family}
All screens: {', '.join(plan.screens)}
Bottom nav tabs: {', '.join(plan.bottom_nav_tabs)}

Requirements:
1. Write COMPLETE Dart code (no TODO or placeholder comments)
2. Use Material 3 design with proper theming (Theme.of(context).colorScheme)
3. Smooth animations (use AnimationController or flutter_animate package)
4. Proper AppBar if needed (not on tabs)
5. Responsive layout (use MediaQuery, LayoutBuilder)
6. All interactive elements work (buttons navigate, forms validate)
7. Proper loading states with shimmer
8. Error states with retry
9. Empty states with illustration
10. Use go_router for navigation: context.goNamed(Routes.screenName)
11. Import needed packages (google_fonts, flutter_animate, etc.)
12. Beautiful, premium UI — NOT basic Material widgets
13. Real content (not "Lorem ipsum") matching the app purpose

Specific screen behavior:
- splash: Animated logo + name, auto-navigate to {'onboarding' if plan.has_onboarding else 'home'} after 2.5s
- onboarding: 3-4 beautiful slides, skip/next/get started buttons
- login: Email+password form, social login buttons, forgot password
- signup: Name+email+password, terms checkbox, animated validation
- home: Main screen with content relevant to {plan.app_type}
- profile: User info, stats, settings shortcuts

Return ONLY the complete Dart file. No markdown fences. No explanations."""

        raw  = self._call(prompt)
        code = self._extract(raw)
        # Safety: ensure class name is correct
        if class_name not in code:
            code = code.replace("class HomeScreen", f"class {class_name}")
        return code if code.strip() else self._fallback_screen(
            screen_name, class_name, plan)

    def _fallback_screen(self, screen_name: str, class_name: str,
                          plan: AppPlan) -> str:
        """Minimal working screen as fallback."""
        return f"""import 'package:flutter/material.dart';

class {class_name} extends StatelessWidget {{
  const {class_name}({{super.key}});

  @override
  Widget build(BuildContext context) {{
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: scheme.background,
      appBar: AppBar(
        title: Text('{screen_name.replace("_", " ").title()}',
            style: Theme.of(context).textTheme.titleLarge),
        backgroundColor: scheme.surface,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.construction, size: 80, color: scheme.primary),
            const SizedBox(height: 24),
            Text('{screen_name.replace("_", " ").title()}',
                style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 12),
            Text('Coming soon',
                style: Theme.of(context).textTheme.bodyLarge),
          ],
        ),
      ),
    );
  }}
}}
"""

    # ─────────────────────────────────────────────────────────
    # Bottom Navigation / Shell
    # ─────────────────────────────────────────────────────────
    def gen_nav_shell(self, plan: AppPlan) -> str:
        pkg   = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())
        tabs  = plan.bottom_nav_tabs

        icons = {
            "home":          ("home_rounded",             "home_outlined"),
            "explore":       ("explore_rounded",          "explore_outlined"),
            "search":        ("search_rounded",           "search"),
            "profile":       ("person_rounded",           "person_outline_rounded"),
            "notifications": ("notifications_rounded",    "notifications_none_rounded"),
            "settings":      ("settings_rounded",         "settings_outlined"),
            "chat":          ("chat_bubble_rounded",      "chat_bubble_outline_rounded"),
            "cart":          ("shopping_cart_rounded",    "shopping_cart_outlined"),
            "library":       ("library_music_rounded",    "library_music_outlined"),
            "dashboard":     ("dashboard_rounded",        "dashboard_outlined"),
            "feed":          ("dynamic_feed_rounded",     "dynamic_feed_outlined"),
            "analytics":     ("analytics_rounded",        "analytics_outlined"),
        }
        default_icon = ("circle_rounded", "circle_outlined")

        dests = "\n".join(
            f"""      NavigationDestination(
        icon:         const Icon(Icons.{icons.get(t, default_icon)[1]}),
        selectedIcon: const Icon(Icons.{icons.get(t, default_icon)[0]}),
        label:        '{t.title()}',
      ),"""
            for t in tabs
        )

        tab_screen_imports = "\n".join(
            f"import 'package:{pkg}/features/{t}/presentation/screens/{t}_screen.dart';"
            for t in tabs
        )
        tab_cases = "\n".join(
            f"        case {i}: return const {''.join(w.title() for w in t.split('_'))}Screen();"
            for i, t in enumerate(tabs)
        )

        return f"""import 'package:flutter/material.dart';
{tab_screen_imports}

class AppShell extends StatefulWidget {{
  const AppShell({{super.key}});
  @override State<AppShell> createState() => _AppShellState();
}}

class _AppShellState extends State<AppShell>
    with SingleTickerProviderStateMixin {{
  int _currentIndex = 0;
  late final AnimationController _ac;
  late final Animation<double>    _fadeAnim;

  @override
  void initState() {{
    super.initState();
    _ac       = AnimationController(vsync: this,
                    duration: const Duration(milliseconds: 200));
    _fadeAnim = Tween<double>(begin: 0.0, end: 1.0).animate(
                    CurvedAnimation(parent: _ac, curve: Curves.easeIn));
    _ac.forward();
  }}

  @override
  void dispose() {{ _ac.dispose(); super.dispose(); }}

  Widget _buildScreen(int index) {{
    switch (index) {{
{tab_cases}
      default: return const SizedBox.shrink();
    }}
  }}

  void _onTap(int index) {{
    if (index == _currentIndex) return;
    _ac.reset();
    setState(() => _currentIndex = index);
    _ac.forward();
  }}

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      body: FadeTransition(
        opacity: _fadeAnim,
        child: _buildScreen(_currentIndex),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex:    _currentIndex,
        onDestinationSelected: _onTap,
        destinations: [
{dests}
        ],
      ),
    );
  }}
}}
"""

    # ─────────────────────────────────────────────────────────
    # Auth Service (Firebase)
    # ─────────────────────────────────────────────────────────
    def gen_auth_service(self, plan: AppPlan) -> str:
        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())
        if not plan.use_firebase:
            return self._gen_mock_auth(pkg)

        return f"""import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

class AuthService {{
  final _auth   = FirebaseAuth.instance;
  final _google = GoogleSignIn();

  // Stream of auth state
  Stream<User?> get authStateChanges => _auth.authStateChanges();
  User? get currentUser              => _auth.currentUser;

  // Email + Password
  Future<UserCredential> signUpWithEmail({{
    required String email,
    required String password,
  }}) async {{
    try {{
      return await _auth.createUserWithEmailAndPassword(
          email: email.trim(), password: password);
    }} on FirebaseAuthException catch (e) {{
      throw _mapFirebaseError(e);
    }}
  }}

  Future<UserCredential> signInWithEmail({{
    required String email,
    required String password,
  }}) async {{
    try {{
      return await _auth.signInWithEmailAndPassword(
          email: email.trim(), password: password);
    }} on FirebaseAuthException catch (e) {{
      throw _mapFirebaseError(e);
    }}
  }}

  // Google Sign-In
  Future<UserCredential?> signInWithGoogle() async {{
    try {{
      final googleUser = await _google.signIn();
      if (googleUser == null) return null;
      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken:     googleAuth.idToken,
      );
      return await _auth.signInWithCredential(credential);
    }} on FirebaseAuthException catch (e) {{
      throw _mapFirebaseError(e);
    }}
  }}

  // Password reset
  Future<void> sendPasswordReset(String email) async {{
    await _auth.sendPasswordResetEmail(email: email.trim());
  }}

  // Sign out
  Future<void> signOut() async {{
    await Future.wait([_auth.signOut(), _google.signOut()]);
  }}

  String _mapFirebaseError(FirebaseAuthException e) {{
    switch (e.code) {{
      case 'user-not-found':      return 'No account found with this email.';
      case 'wrong-password':      return 'Incorrect password.';
      case 'email-already-in-use':return 'This email is already registered.';
      case 'weak-password':       return 'Password must be at least 6 characters.';
      case 'invalid-email':       return 'Please enter a valid email.';
      case 'too-many-requests':   return 'Too many attempts. Try again later.';
      default:                    return e.message ?? 'Authentication failed.';
    }}
  }}
}}
"""

    def _gen_mock_auth(self, pkg: str) -> str:
        return f"""import 'package:shared_preferences/shared_preferences.dart';

class AuthService {{
  static const _keyLoggedIn = 'is_logged_in';
  static const _keyEmail    = 'user_email';

  Future<bool> get isLoggedIn async {{
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyLoggedIn) ?? false;
  }}

  Future<void> signIn(String email, String password) async {{
    // TODO: replace with real API call
    if (email.isEmpty || password.length < 6)
      throw 'Invalid credentials';
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyLoggedIn, true);
    await prefs.setString(_keyEmail, email);
  }}

  Future<void> signOut() async {{
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyLoggedIn);
    await prefs.remove(_keyEmail);
  }}
}}
"""

    # ─────────────────────────────────────────────────────────
    # App Constants
    # ─────────────────────────────────────────────────────────
    def gen_constants(self, plan: AppPlan) -> str:
        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())
        return f"""class AppConstants {{
  // App info
  static const appName    = '{plan.app_name}';
  static const appVersion = '1.0.0';
  static const packageId  = '{plan.package_name}';

  // API
  static const apiBaseUrl   = '{plan.api_base_url or "https://api.example.com/v1"}';
  static const apiTimeout   = Duration(seconds: 30);
  static const cacheTimeout = Duration(minutes: 5);

  // Pagination
  static const pageSize = 20;

  // Storage keys
  static const keyThemeMode   = 'theme_mode';
  static const keyOnboarded   = 'onboarded';
  static const keyAuthToken   = 'auth_token';
  static const keyUserData    = 'user_data';

  // Animation durations
  static const durationFast   = Duration(milliseconds: 200);
  static const durationNormal = Duration(milliseconds: 350);
  static const durationSlow   = Duration(milliseconds: 600);

  // UI
  static const borderRadius = 16.0;
  static const paddingPage  = 20.0;
  static const paddingCard  = 16.0;
}}
"""

    # ─────────────────────────────────────────────────────────
    # README
    # ─────────────────────────────────────────────────────────
    def gen_readme(self, plan: AppPlan) -> str:
        arch = plan.get_arch()
        pkgs = plan.get_packages()
        return f"""# {plan.app_name}
> {plan.tagline or plan.app_description[:100]}

Built with **JARVIS App Builder** — AI-powered Flutter generator.

## Architecture
**{arch['name']}** — {arch['description']}
Pattern: {plan.pattern.upper()}
State Management: {plan.state_mgmt}

## Tech Stack
- Flutter 3.22+
- Dart 3.4+
- {arch['name']}
{chr(10).join(f'- {p}' for p in pkgs[:10])}

## Quick Start

### Prerequisites
```bash
flutter --version    # Must be 3.22+
dart --version       # Must be 3.4+
```

### Run App
```bash
flutter pub get
flutter run
```

### Build APK
```bash
flutter build apk --release
# Output: build/app/outputs/flutter-apk/app-release.apk
```

### Build AAB (Play Store)
```bash
flutter build appbundle --release
```

## Screens
{chr(10).join(f'- {s.replace("_", " ").title()}' for s in plan.screens)}

## Project Structure
```
lib/
├── main.dart
├── core/
│   ├── theme/        # AppTheme, AppColors
│   ├── router/       # GoRouter config
│   ├── constants/    # AppConstants
│   └── utils/        # Helpers
├── features/
│   ├── auth/         # Login, Signup
│   ├── home/         # Home screen
│   └── ...           # Other features
└── shared/
    ├── widgets/      # Reusable widgets
    └── models/       # Data models
```

## Generated by JARVIS
Auto-generated by JARVIS AI App Builder — production-ready Flutter app.
"""
