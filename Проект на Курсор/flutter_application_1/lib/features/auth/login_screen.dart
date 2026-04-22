import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../application/providers.dart';
import '../../common/widgets/global_market_logo.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_spacing.dart';

/// Вход по логину и паролю (демо).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _loginCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _loginFocus = FocusNode();
  final _passFocus = FocusNode();
  var _obscure = true;
  var _loading = false;
  String? _error;

  @override
  void dispose() {
    _loginCtrl.dispose();
    _passCtrl.dispose();
    _loginFocus.dispose();
    _passFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _error = null;
      _loading = true;
    });
    try {
      await ref.read(appSessionProvider.notifier).signIn(
            _loginCtrl.text,
            _passCtrl.text,
          );
      if (!mounted) return;
      final from = GoRouterState.of(context).uri.queryParameters['from'];
      if (from != null && from.isNotEmpty) {
        context.go(Uri.decodeComponent(from));
      } else {
        context.go('/home');
      }
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.paddingOf(context).bottom;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: const Alignment(0, -0.35),
                  radius: 1.15,
                  colors: [
                    AppColors.accent.withValues(alpha: 0.14),
                    AppColors.background,
                    AppColors.background,
                  ],
                  stops: const [0.0, 0.45, 1.0],
                ),
              ),
            ),
          ),
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.lg,
                  AppSpacing.xl,
                  AppSpacing.lg,
                  AppSpacing.lg + bottomInset,
                ),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 400),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 8),
                      Center(
                        child: GlobalMarketLogo(
                          crossAxisAlignment: CrossAxisAlignment.center,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'премиальная витрина техники',
                        textAlign: TextAlign.center,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          letterSpacing: 2.4,
                          fontWeight: FontWeight.w500,
                          color: AppColors.textTertiary,
                        ),
                      ),
                      const SizedBox(height: 48),
                      _fieldLabel('Логин'),
                      const SizedBox(height: 10),
                      _input(
                        controller: _loginCtrl,
                        focusNode: _loginFocus,
                        hint: 'Введите логин',
                        textInputAction: TextInputAction.next,
                        onSubmitted: (_) => _passFocus.requestFocus(),
                        obscure: false,
                      ),
                      const SizedBox(height: 22),
                      _fieldLabel('Пароль'),
                      const SizedBox(height: 10),
                      _input(
                        controller: _passCtrl,
                        focusNode: _passFocus,
                        hint: 'Введите пароль',
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _submit(),
                        obscure: _obscure,
                        suffix: IconButton(
                          onPressed: () => setState(() => _obscure = !_obscure),
                          icon: Icon(
                            _obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                            color: AppColors.textSecondary,
                            size: 22,
                          ),
                        ),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: AppColors.danger,
                                height: 1.35,
                              ),
                        ),
                      ],
                      const SizedBox(height: 36),
                      SizedBox(
                        height: 54,
                        child: FilledButton(
                          onPressed: _loading ? null : _submit,
                          style: FilledButton.styleFrom(
                            backgroundColor: AppColors.accent,
                            foregroundColor: Colors.black,
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                            ),
                          ),
                          child: _loading
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.black,
                                  ),
                                )
                              : Text(
                                  'Войти',
                                  style: GoogleFonts.inter(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _fieldLabel(String text) {
    return Text(
      text.toUpperCase(),
      textAlign: TextAlign.center,
      style: GoogleFonts.inter(
        fontSize: 11,
        letterSpacing: 2,
        fontWeight: FontWeight.w600,
        color: AppColors.textSecondary,
      ),
    );
  }

  Widget _input({
    required TextEditingController controller,
    required FocusNode focusNode,
    required String hint,
    required TextInputAction textInputAction,
    required void Function(String) onSubmitted,
    required bool obscure,
    Widget? suffix,
  }) {
    return TextField(
      controller: controller,
      focusNode: focusNode,
      obscureText: obscure,
      textInputAction: textInputAction,
      onSubmitted: onSubmitted,
      style: GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w500,
        color: AppColors.textPrimary,
        letterSpacing: 0.2,
      ),
      cursorColor: AppColors.accent,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GoogleFonts.inter(
          color: AppColors.textTertiary,
          fontWeight: FontWeight.w400,
        ),
        filled: true,
        fillColor: AppColors.surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
        suffixIcon: suffix,
      ),
    );
  }
}
