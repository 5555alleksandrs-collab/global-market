import 'package:equatable/equatable.dart';

/// Универсальные характеристики техники (расширяемо под API).
class TechSpecs extends Equatable {
  const TechSpecs({
    this.storage,
    this.color,
    this.region,
    this.simType,
    this.chipset,
    this.displaySize,
    this.battery,
    this.connectivity,
    this.warranty,
    this.condition,
    this.extra,
  });

  final String? storage;
  final String? color;
  final String? region;
  final String? simType;
  final String? chipset;
  final String? displaySize;
  final String? battery;
  final String? connectivity;
  final String? warranty;
  final String? condition;

  /// Доп. пары ключ-значение для редких полей.
  final Map<String, String>? extra;

  Map<String, String> toDisplayMap() {
    final m = <String, String>{};
    void put(String label, String? v) {
      if (v != null && v.isNotEmpty) m[label] = v;
    }

    put('Память', storage);
    put('Цвет', color);
    put('Регион', region);
    put('SIM', simType);
    put('Чип', chipset);
    put('Дисплей', displaySize);
    put('Аккумулятор', battery);
    put('Связь', connectivity);
    put('Гарантия', warranty);
    put('Состояние', condition);
    if (extra != null) m.addAll(extra!);
    return m;
  }

  factory TechSpecs.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const TechSpecs();
    return TechSpecs(
      storage: json['storage'] as String?,
      color: json['color'] as String?,
      region: json['region'] as String?,
      simType: json['simType'] as String?,
      chipset: json['chipset'] as String?,
      displaySize: json['displaySize'] as String?,
      battery: json['battery'] as String?,
      connectivity: json['connectivity'] as String?,
      warranty: json['warranty'] as String?,
      condition: json['condition'] as String?,
      extra: (json['extra'] as Map<String, dynamic>?)
          ?.map((k, v) => MapEntry(k, v.toString())),
    );
  }

  Map<String, dynamic> toJson() => {
        'storage': storage,
        'color': color,
        'region': region,
        'simType': simType,
        'chipset': chipset,
        'displaySize': displaySize,
        'battery': battery,
        'connectivity': connectivity,
        'warranty': warranty,
        'condition': condition,
        'extra': extra,
      };

  @override
  List<Object?> get props => [
        storage,
        color,
        region,
        simType,
        chipset,
        displaySize,
        battery,
        connectivity,
        warranty,
        condition,
        extra,
      ];
}
