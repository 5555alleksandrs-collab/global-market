import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../application/providers.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/router/safe_navigation.dart';
import '../../core/domain/models/product.dart';
import '../../core/domain/models/tech_specs.dart';
import '../../core/theme/admin_theme.dart';
import 'widgets/admin_section_card.dart';

/// Редактирование или создание товара. Маршрут: `/admin/product?id=...` или без id.
class AdminProductEditScreen extends ConsumerStatefulWidget {
  const AdminProductEditScreen({super.key, this.productId});

  final String? productId;

  @override
  ConsumerState<AdminProductEditScreen> createState() => _AdminProductEditScreenState();
}

class _AdminProductEditScreenState extends ConsumerState<AdminProductEditScreen> {
  final _name = TextEditingController();
  final _sku = TextEditingController();
  final _price = TextEditingController();
  final _oldPrice = TextEditingController();
  final _currency = TextEditingController();
  final _rating = TextEditingController();
  final _description = TextEditingController();
  final _images = TextEditingController();
  final _stockQty = TextEditingController();

  String? _categoryId;
  String? _brandId;
  bool _isPopular = false;
  bool _isNew = false;

  Product? _base;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _name.dispose();
    _sku.dispose();
    _price.dispose();
    _oldPrice.dispose();
    _currency.dispose();
    _rating.dispose();
    _description.dispose();
    _images.dispose();
    _stockQty.dispose();
    super.dispose();
  }

  Product _newProduct() {
    return Product(
      id: const Uuid().v4(),
      name: '',
      categoryId: 'iphone',
      brandId: 'apple',
      price: 0,
      currency: 'RUB',
      images: ['https://picsum.photos/seed/newproduct/800/1000'],
      description: '',
      specifications: const TechSpecs(),
      inStock: true,
      stockQuantity: 5,
      rating: 4.5,
      isPopular: false,
      isNew: true,
      variants: const [],
      sku: 'SKU-${DateTime.now().millisecondsSinceEpoch}',
    );
  }

  void _fillFrom(Product p) {
    _base = p;
    _name.text = p.name;
    _sku.text = p.sku;
    _price.text = p.price.toStringAsFixed(p.price == p.price.roundToDouble() ? 0 : 2);
    _oldPrice.text = p.oldPrice != null ? p.oldPrice!.toStringAsFixed(0) : '';
    _currency.text = p.currency;
    _rating.text = p.rating.toStringAsFixed(1);
    _description.text = p.description;
    _images.text = p.images.join('\n');
    _stockQty.text = '${p.stockQuantity}';
    _categoryId = p.categoryId;
    _brandId = p.brandId;
    _isPopular = p.isPopular;
    _isNew = p.isNew;
  }

  int _parseStock() {
    final t = _stockQty.text.trim();
    if (t.isEmpty) return 0;
    return int.tryParse(t) ?? 0;
  }

  void _bumpStock(int delta) {
    final v = _parseStock() + delta;
    setState(() {
      _stockQty.text = '${v.clamp(0, 999999)}';
    });
  }

  Future<void> _load() async {
    final id = widget.productId;
    try {
      if (id == null || id.isEmpty) {
        final p = _newProduct();
        if (mounted) {
          setState(() {
            _fillFrom(p);
            _loading = false;
          });
        }
        return;
      }
      final repo = ref.read(catalogRepositoryProvider);
      final p = await repo.getProductById(id);
      if (!mounted) return;
      if (p == null) {
        setState(() {
          _error = 'Товар не найден';
          _loading = false;
        });
        return;
      }
      setState(() {
        _fillFrom(p);
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  Future<void> _save() async {
    if (_base == null) return;
    final price = double.tryParse(_price.text.replaceAll(',', '.')) ?? 0;
    final oldP = _oldPrice.text.trim().isEmpty ? null : double.tryParse(_oldPrice.text.replaceAll(',', '.'));
    final rating = double.tryParse(_rating.text.replaceAll(',', '.')) ?? 0;
    final stock = _parseStock().clamp(0, 999999);
    final imgs = _images.text
        .split('\n')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    if (imgs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Добавьте хотя бы один URL картинки')),
      );
      return;
    }
    if (_categoryId == null || _brandId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Выберите категорию и бренд')),
      );
      return;
    }

    final updated = _base!.copyWith(
      name: _name.text.trim(),
      sku: _sku.text.trim(),
      categoryId: _categoryId,
      brandId: _brandId,
      price: price,
      oldPrice: oldP,
      clearOldPrice: _oldPrice.text.trim().isEmpty,
      currency: _currency.text.trim().isEmpty ? 'RUB' : _currency.text.trim(),
      description: _description.text.trim(),
      images: imgs,
      stockQuantity: stock,
      inStock: stock > 0,
      rating: rating,
      isPopular: _isPopular,
      isNew: _isNew,
    );

    await ref.read(adminCatalogServiceProvider).upsertProduct(updated);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Сохранено')));
      popOrGo(context, fallback: '/admin');
    }
  }

  @override
  Widget build(BuildContext context) {
    final categories = ref.watch(categoriesProvider);
    final brands = ref.watch(brandsProvider);

    if (_loading) {
      return Scaffold(
        backgroundColor: AdminTheme.canvas,
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null) {
      return Scaffold(
        backgroundColor: AdminTheme.canvas,
        appBar: AppBar(title: const Text('Ошибка')),
        body: Center(child: Text(_error!)),
      );
    }

    final stock = _parseStock();
    final stockLabel = stock <= 0 ? 'Нет в наличии' : '$stock шт. на складе';

    return Scaffold(
      backgroundColor: AdminTheme.canvas,
      appBar: AppBar(
        title: Text(widget.productId == null || widget.productId!.isEmpty ? 'Новый товар' : 'Редактирование'),
        actions: [
          FilledButton.icon(
            onPressed: _save,
            icon: const Icon(Icons.save_rounded, size: 20),
            label: const Text('Сохранить'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          AdminSectionCard(
            title: 'Основное',
            subtitle: 'Название, артикул и категория',
            icon: Icons.label_outline_rounded,
            iconColor: AdminTheme.primary,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _name,
                  decoration: const InputDecoration(labelText: 'Название *'),
                ),
                const SizedBox(height: AppSpacing.sm),
                TextField(
                  controller: _sku,
                  decoration: const InputDecoration(labelText: 'SKU *'),
                ),
                const SizedBox(height: AppSpacing.sm),
                categories.when(
                  data: (cats) {
                    return DropdownButtonFormField<String>(
                      value: _categoryId,
                      decoration: const InputDecoration(labelText: 'Категория *'),
                      items: cats
                          .map(
                            (c) => DropdownMenuItem(
                              value: c.id,
                              child: Text(c.name),
                            ),
                          )
                          .toList(),
                      onChanged: (v) => setState(() => _categoryId = v),
                    );
                  },
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text('Ошибка категорий: $e'),
                ),
                const SizedBox(height: AppSpacing.sm),
                brands.when(
                  data: (bs) {
                    return DropdownButtonFormField<String>(
                      value: _brandId,
                      decoration: const InputDecoration(labelText: 'Бренд *'),
                      items: bs
                          .map(
                            (b) => DropdownMenuItem(
                              value: b.id,
                              child: Text(b.name),
                            ),
                          )
                          .toList(),
                      onChanged: (v) => setState(() => _brandId = v),
                    );
                  },
                  loading: () => const SizedBox.shrink(),
                  error: (e, _) => Text('Ошибка брендов: $e'),
                ),
              ],
            ),
          ),
          AdminSectionCard(
            title: 'Цена и наличие',
            subtitle: 'Остаток в штуках — витрина показывает «в наличии», если количество > 0',
            icon: Icons.payments_outlined,
            iconColor: const Color(0xFF059669),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _price,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'Цена *'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: _oldPrice,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'Старая цена'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                TextField(
                  controller: _currency,
                  decoration: const InputDecoration(labelText: 'Валюта'),
                ),
                const SizedBox(height: AppSpacing.lg),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: stock > 0
                        ? AdminTheme.success.withValues(alpha: 0.08)
                        : const Color(0xFFFEE2E2),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: stock > 0
                          ? AdminTheme.success.withValues(alpha: 0.35)
                          : const Color(0xFFFECACA),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        stock > 0 ? Icons.inventory_2_rounded : Icons.remove_shopping_cart_rounded,
                        color: stock > 0 ? AdminTheme.success : AdminTheme.danger,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Остаток на складе',
                              style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            Text(
                              stockLabel,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: const Color(0xFF64748B),
                                  ),
                            ),
                          ],
                        ),
                      ),
                      IconButton.filled(
                        style: IconButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: AdminTheme.primary,
                        ),
                        onPressed: stock > 0 ? () => _bumpStock(-1) : null,
                        icon: const Icon(Icons.remove_rounded),
                      ),
                      SizedBox(
                        width: 72,
                        child: TextField(
                          controller: _stockQty,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          textAlign: TextAlign.center,
                          decoration: const InputDecoration(
                            isDense: true,
                            contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                          ),
                          onChanged: (_) => setState(() {}),
                        ),
                      ),
                      IconButton.filled(
                        style: IconButton.styleFrom(
                          backgroundColor: AdminTheme.primary,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: () => _bumpStock(1),
                        icon: const Icon(Icons.add_rounded),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          AdminSectionCard(
            title: 'Маркетинг',
            subtitle: 'Бейджи и рейтинг',
            icon: Icons.trending_up_rounded,
            iconColor: const Color(0xFFEA580C),
            child: Column(
              children: [
                TextField(
                  controller: _rating,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Рейтинг (0–5)'),
                ),
                const SizedBox(height: AppSpacing.sm),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Популярный'),
                  value: _isPopular,
                  onChanged: (v) => setState(() => _isPopular = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Новинка'),
                  value: _isNew,
                  onChanged: (v) => setState(() => _isNew = v),
                ),
              ],
            ),
          ),
          AdminSectionCard(
            title: 'Медиа и описание',
            subtitle: 'Ссылки на изображения — по одному в строке',
            icon: Icons.photo_library_outlined,
            iconColor: const Color(0xFF7C3AED),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _images,
                  minLines: 3,
                  maxLines: 8,
                  decoration: const InputDecoration(
                    alignLabelWithHint: true,
                    hintText: 'https://...\nhttps://...',
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                TextField(
                  controller: _description,
                  minLines: 3,
                  maxLines: 10,
                  decoration: const InputDecoration(labelText: 'Описание'),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  'Варианты и детальные характеристики пока берутся из исходного товара; расширенный редактор — при подключении API.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFF94A3B8)),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xxl),
        ],
      ),
    );
  }
}
