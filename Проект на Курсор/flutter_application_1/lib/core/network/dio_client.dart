import 'package:dio/dio.dart';

import '../errors/app_exception.dart';

/// Базовый HTTP-клиент для будущего API. Сейчас не используется каталогом (mock).
class DioClient {
  DioClient({String? baseUrl}) {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl ?? 'https://api.example.com',
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 20),
        headers: const {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      ),
    );
    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (e, handler) {
          handler.reject(e);
        },
      ),
    );
  }

  late final Dio _dio;

  Dio get raw => _dio;

  /// Замените [baseUrl] при подключении реального backend.
  void updateBaseUrl(String baseUrl) {
    _dio.options.baseUrl = baseUrl;
  }

  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      return await _dio.get<T>(path, queryParameters: queryParameters);
    } on DioException catch (e) {
      throw AppException(_mapDio(e), cause: e);
    }
  }

  String _mapDio(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout) {
      return 'Нет соединения с сервером';
    }
    if (e.response?.statusCode == 401) {
      return 'Требуется авторизация';
    }
    return e.message ?? 'Ошибка сети';
  }
}
