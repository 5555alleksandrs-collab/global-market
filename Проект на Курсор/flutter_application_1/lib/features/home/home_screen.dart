import 'dart:convert';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../application/providers.dart';
import '../../common/widgets/app_states.dart';
import '../../common/widgets/global_market_logo.dart';
import '../../common/widgets/product_card.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_shadows.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/domain/models/banner_slide.dart';
import '../../core/domain/models/product.dart';

final bannersProvider = FutureProvider<List<BannerSlide>>((ref) async {
  final raw = await rootBundle.loadString('assets/mock/banners.json');
  final list = jsonDecode(raw) as List<dynamic>;
  return list.map((e) => BannerSlide.fromJson(e as Map<String, dynamic>)).toList();
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(allProductsProvider);
    final categories = ref.watch(categoriesProvider);
    final banners = ref.watch(bannersProvider);

    return Scaffold(
      drawer: _AppDrawer(),
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            toolbarHeight: 52,
            surfaceTintColor: Colors.transparent,
            leading: Builder(
              builder: (context) => IconButton(
                icon: const Icon(Icons.menu_rounded),
                onPressed: () => Scaffold.of(context).openDrawer(),
              ),
            ),
            title: const GlobalMarketLogo(compact: true),
            centerTitle: true,
            actions: [
              IconButton(
                tooltip: 'Город',
                onPressed: () {},
                icon: const Icon(Icons.location_on_rounded, color: AppColors.accent),
              ),
            ],
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
              child: _SearchBar(onTap: () => context.go('/catalog')),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
              child: banners.when(
                data: (b) => _BannerCarousel(banners: b),
                loading: () => const SizedBox(height: 180, child: AppLoading()),
                error: (e, _) => AppErrorState(
                  message: 'Не удалось загрузить баннеры',
                  onRetry: () => ref.invalidate(bannersProvider),
                ),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: Row(
                children: [
                  Container(
                    width: 4,
                    height: 22,
                    decoration: BoxDecoration(
                      color: AppColors.accent,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text('Категории', style: Theme.of(context).textTheme.titleLarge),
                ],
              ),
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.sm)),
          categories.when(
            data: (cats) => SliverToBoxAdapter(
              child: SizedBox(
                height: 110,
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  scrollDirection: Axis.horizontal,
                  itemBuilder: (context, i) {
                    final c = cats[i];
                    return _CategoryChip(
                      label: c.name,
                      onTap: () => context.push('/category/${c.id}'),
                    );
                  },
                  separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.sm),
                  itemCount: cats.length,
                ),
              ),
            ),
            loading: () => const SliverToBoxAdapter(child: SizedBox(height: 110, child: AppLoading())),
            error: (e, _) => SliverToBoxAdapter(
              child: AppErrorState(
                message: 'Ошибка категорий',
                onRetry: () => ref.invalidate(categoriesProvider),
              ),
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.lg)),
          products.when(
            data: (all) {
              final popular = all.where((p) => p.isPopular).take(8).toList();
              final fresh = all.where((p) => p.isNew).take(8).toList();
              final rec = all.where((p) => p.rating >= 4.6).take(8).toList();
              return SliverList(
                delegate: SliverChildListDelegate([
                  _SectionHeader(
                    title: 'Популярные товары',
                    onSeeAll: () => context.go('/catalog'),
                  ),
                  _ProductRow(products: popular),
                  const SizedBox(height: AppSpacing.lg),
                  _SectionHeader(
                    title: 'Новинки',
                    onSeeAll: () => context.go('/catalog'),
                  ),
                  _ProductRow(products: fresh),
                  const SizedBox(height: AppSpacing.lg),
                  _SectionHeader(
                    title: 'Рекомендуем',
                    onSeeAll: () => context.go('/catalog'),
                  ),
                  _ProductRow(products: rec),
                  const SizedBox(height: AppSpacing.xxl),
                ]),
              );
            },
            loading: () => const SliverToBoxAdapter(
              child: SizedBox(
                height: 320,
                child: AppLoading(message: 'Загрузка каталога…'),
              ),
            ),
            error: (e, _) => SliverToBoxAdapter(
              child: SizedBox(
                height: 280,
                child: AppErrorState(
                  message: 'Не удалось загрузить каталог',
                  onRetry: () => ref.invalidate(allProductsProvider),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          child: Row(
            children: [
              const Icon(Icons.search_rounded, color: AppColors.textTertiary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Поиск по каталогу',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textTertiary),
                ),
              ),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: const BoxDecoration(
                  color: AppColors.accent,
                  borderRadius: BorderRadius.all(Radius.circular(10)),
                ),
                child: const Icon(Icons.search_rounded, color: Colors.white, size: 20),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AppDrawer extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: AppColors.background,
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Scaffold.of(context).closeDrawer(),
                ),
                const Expanded(
                  child: Center(
                    child: GlobalMarketLogo(compact: true),
                  ),
                ),
                const SizedBox(width: 48),
              ],
            ),
            const SizedBox(height: 24),
            ListTile(
              leading: const Icon(Icons.percent_rounded, color: AppColors.accent),
              title: const Text('Акции и скидки'),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.go('/catalog');
              },
            ),
            ListTile(
              leading: const Icon(Icons.info_outline_rounded, color: AppColors.accent),
              title: const Text('О компании и правила'),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.push('/company');
              },
            ),
            ListTile(
              leading: const Icon(Icons.receipt_long_rounded, color: AppColors.accent),
              title: const Text('Мои заказы'),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.push('/orders');
              },
            ),
            ListTile(
              leading: const Icon(Icons.person_outline_rounded, color: AppColors.accent),
              title: const Text('Профиль'),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.go('/profile');
              },
            ),
            const Divider(color: AppColors.border),
            ListTile(
              leading: const Icon(Icons.grid_view_rounded, color: AppColors.textSecondary),
              title: const Text('Каталог'),
              onTap: () {
                Scaffold.of(context).closeDrawer();
                context.go('/catalog');
              },
            ),
            const SizedBox(height: 24),
            Text(
              'Оптовая продажа техники и аксессуаров',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
      ),
    );
  }
}

class _BannerCarousel extends StatefulWidget {
  const _BannerCarousel({required this.banners});

  final List<BannerSlide> banners;

  @override
  State<_BannerCarousel> createState() => _BannerCarouselState();
}

class _BannerCarouselState extends State<_BannerCarousel> {
  final _controller = PageController(viewportFraction: 0.92);
  int _page = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final banners = widget.banners;
    if (banners.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      children: [
        SizedBox(
          height: 190,
          child: PageView.builder(
            controller: _controller,
            itemCount: banners.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (context, i) {
              final b = banners[i];
              return Padding(
                padding: const EdgeInsets.only(right: AppSpacing.sm),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: AppShadows.banner,
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(24),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        CachedNetworkImage(
                          imageUrl: b.imageUrl,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => Container(color: AppColors.chip),
                        ),
                        Container(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                Colors.black.withValues(alpha: 0.05),
                                Colors.black.withValues(alpha: 0.65),
                              ],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                          ),
                        ),
                        Positioned(
                          left: 16,
                          right: 16,
                          bottom: 16,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                b.title,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.4,
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                b.subtitle,
                                style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.92),
                                  fontSize: 13,
                                  height: 1.35,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Positioned.fill(
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () {
                                final link = b.deepLink;
                                if (link == null) return;
                                if (link.startsWith('/category/')) {
                                  context.push(link);
                                } else if (link == '/catalog') {
                                  context.go('/catalog');
                                }
                              },
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(
            banners.length,
            (i) => AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.symmetric(horizontal: 3),
              height: 6,
              width: i == _page ? 18 : 6,
              decoration: BoxDecoration(
                color: i == _page ? AppColors.accent : AppColors.border.withValues(alpha: 0.7),
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _CategoryChip extends StatelessWidget {
  const _CategoryChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Ink(
          width: 152,
          height: 110,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.border.withValues(alpha: 0.55)),
            boxShadow: AppShadows.card,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.accentSoft,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.grid_view_rounded, color: AppColors.accent, size: 20),
              ),
              Text(
                label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      height: 1.15,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.onSeeAll});

  final String title;
  final VoidCallback onSeeAll;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                  ),
            ),
          ),
          TextButton(
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              backgroundColor: AppColors.accentSoft,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: onSeeAll,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Все', style: Theme.of(context).textTheme.labelLarge?.copyWith(color: AppColors.accent)),
                const SizedBox(width: 2),
                const Icon(Icons.chevron_right_rounded, size: 18, color: AppColors.accent),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductRow extends StatelessWidget {
  const _ProductRow({required this.products});

  final List<Product> products;

  @override
  Widget build(BuildContext context) {
    if (products.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
        child: AppEmptyState(
          title: 'Пока пусто',
          subtitle: 'Попробуйте позже — мы обновляем подборку.',
        ),
      );
    }

    return SizedBox(
      height: 300,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        scrollDirection: Axis.horizontal,
        itemCount: products.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.sm),
        itemBuilder: (context, i) => SizedBox(
          width: 220,
          child: ProductCard(product: products[i], compact: true),
        ),
      ),
    );
  }
}
