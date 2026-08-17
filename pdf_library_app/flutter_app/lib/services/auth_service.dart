import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Gère l'inscription, la connexion et le jeton JWT stocké de façon sécurisée
/// sur l'appareil (Keychain sur iOS, Keystore sur Android).
class AuthService {
  AuthService({required this.baseUrl});

  final String baseUrl;
  final _storage = const FlutterSecureStorage();
  static const _tokenKey = 'access_token';

  Future<String?> get token => _storage.read(key: _tokenKey);

  Future<bool> isLoggedIn() async => (await token) != null;

  Future<void> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'display_name': displayName,
      }),
    );
    if (response.statusCode != 201) {
      throw Exception(_extractError(response));
    }
    // Inscription réussie : on connecte directement l'utilisateur.
    await login(email: email, password: password);
  }

  Future<void> login({required String email, required String password}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (response.statusCode != 200) {
      throw Exception(_extractError(response));
    }
    final data = jsonDecode(response.body);
    await _storage.write(key: _tokenKey, value: data['access_token'] as String);
  }

  Future<void> logout() async {
    await _storage.delete(key: _tokenKey);
  }

  Future<Map<String, String>> authHeaders() async {
    final t = await token;
    if (t == null) return {};
    return {'Authorization': 'Bearer $t'};
  }

  String _extractError(http.Response response) {
    try {
      final data = jsonDecode(response.body);
      return data['detail'] as String? ?? 'Erreur inconnue (${response.statusCode}).';
    } catch (_) {
      return 'Erreur inconnue (${response.statusCode}).';
    }
  }
}
