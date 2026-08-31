/**
 * LinkedLeads.ai — Content Script (runs on linkedin.com)
 * Executes LinkedIn actions using the Voyager API from the user's real browser session.
 */

(() => {
  'use strict';

  // Notify background we're on LinkedIn
  chrome.runtime.sendMessage({ type: 'LINKEDIN_SESSION_DETECTED' }).catch(() => {});

  // ============ CSRF Token ============
  function getCsrfToken(fallback) {
    // Try meta tag first
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;
    // Try cookie
    const match = document.cookie.match(/JSESSIONID="?([^";]+)/);
    if (match) return match[1].replace(/"/g, '');
    return fallback || '';
  }

  // ============ Voyager API Helpers ============
  const VOYAGER_BASE = 'https://www.linkedin.com/voyager/api';

  async function voyagerFetch(endpoint, options = {}) {
    const csrfToken = getCsrfToken(options.csrfToken);
    const resp = await fetch(`${VOYAGER_BASE}${endpoint}`, {
      ...options,
      headers: {
        'csrf-token': csrfToken,
        'x-restli-protocol-version': '2.0.0',
        ...(options.headers || {}),
      },
      credentials: 'include',
    });
    return resp;
  }

  // ============ Resolve Profile URN ============
  async function resolveProfileUrn(publicId, csrfToken) {
    try {
      const resp = await voyagerFetch(
        `/identity/dash/profiles?q=memberIdentity&memberIdentity=${publicId}&decorationId=com.linkedin.voyager.dash.deco.identity.profile.WebFullProfileWithFamily-12`,
        { csrfToken }
      );
      if (resp.ok) {
        const data = await resp.json();
        const elements = data?.included || [];
        for (const el of elements) {
          if (el['$type'] === 'com.linkedin.voyager.dash.identity.profile.Profile' ||
              el['entityUrn']?.includes('fsd_profile')) {
            return el.entityUrn;
          }
        }
        // Fallback: extract from any profileId match
        for (const el of elements) {
          if (el.entityUrn && el.entityUrn.includes('fsd_profile')) {
            return el.entityUrn;
          }
        }
      }
    } catch (e) {
      console.error('[LinkedLeads] URN resolve error:', e);
    }
    // Construct URN from miniProfile if available
    return null;
  }

  // ============ Get Mini Profile ============
  async function getMiniProfile(publicId, csrfToken) {
    try {
      const resp = await voyagerFetch(
        `/identity/profiles/${publicId}/profileView`,
        { csrfToken }
      );
      if (resp.ok) {
        const data = await resp.json();
        const elements = data?.included || [];
        let miniProfile = null;
        let entityUrn = null;
        for (const el of elements) {
          if (el['$type'] === 'com.linkedin.voyager.identity.shared.MiniProfile' && el.publicIdentifier === publicId) {
            miniProfile = el;
            entityUrn = el.entityUrn; // urn:li:fs_miniProfile:XXXX
            break;
          }
        }
        return { miniProfile, entityUrn, fullData: data };
      }
    } catch (e) {
      console.error('[LinkedLeads] getMiniProfile error:', e);
    }
    return null;
  }

  // ============ Send Connection Request ============
  async function sendConnectionRequest(publicId, message, csrfToken) {
    // First, try to get the profile info
    const profileData = await getMiniProfile(publicId, csrfToken);
    const trackingId = generateTrackingId();
    
    const body = {
      invitee: {
        'com.linkedin.voyager.growth.invitation.InviteeProfile': {
          profileId: publicId,
        }
      },
      trackingId: trackingId,
    };
    
    // Add message if provided (max 300 chars for connection notes)
    if (message && message.trim()) {
      body.message = message.trim().substring(0, 300);
    }

    const resp = await voyagerFetch('/growth/normInvitations', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      csrfToken,
    });

    if (resp.ok || resp.status === 201) {
      return { success: true, action: 'connect', publicId };
    }

    const errText = await resp.text();
    
    // Handle "already connected" or "invitation pending"
    if (resp.status === 422 || errText.includes('already') || errText.includes('pending')) {
      return { success: true, action: 'connect', publicId, note: 'Already connected or invitation pending' };
    }
    
    return { success: false, error: `Connection request failed: ${resp.status} - ${errText}`, publicId };
  }

  // ============ Send Message ============
  async function sendMessage(publicId, message, csrfToken) {
    // Get profile URN
    const profileData = await getMiniProfile(publicId, csrfToken);
    if (!profileData || !profileData.entityUrn) {
      return { success: false, error: 'Could not resolve profile URN', publicId };
    }

    // Extract member ID from entityUrn (urn:li:fs_miniProfile:XXXXX)
    const memberId = profileData.entityUrn.split(':').pop();

    // Try LEGACY_INBOX first (more reliable)
    const body = {
      keyVersion: 'LEGACY_INBOX',
      conversationCreate: {
        eventCreate: {
          value: {
            'com.linkedin.voyager.messaging.create.MessageCreate': {
              body: message,
              attachments: [],
            }
          }
        },
        recipients: [`urn:li:fs_miniProfile:${memberId}`],
        subtype: 'MEMBER_TO_MEMBER',
      }
    };

    const resp = await voyagerFetch('/messaging/conversations', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      csrfToken,
    });

    if (resp.ok || resp.status === 201) {
      return { success: true, action: 'message', publicId };
    }

    const errText = await resp.text();
    
    // If LEGACY_INBOX fails, try regular
    if (resp.status >= 400) {
      const altBody = {
        conversationCreate: {
          eventCreate: {
            value: {
              'com.linkedin.voyager.messaging.create.MessageCreate': {
                body: message,
                attachments: [],
              }
            }
          },
          recipients: [`urn:li:fs_miniProfile:${memberId}`],
          subtype: 'MEMBER_TO_MEMBER',
        }
      };

      const altResp = await voyagerFetch('/messaging/conversations', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(altBody),
        csrfToken,
      });

      if (altResp.ok || altResp.status === 201) {
        return { success: true, action: 'message', publicId };
      }
      const altErr = await altResp.text();
      return { success: false, error: `Message failed: ${altResp.status} - ${altErr}`, publicId };
    }

    return { success: false, error: `Message failed: ${resp.status} - ${errText}`, publicId };
  }

  // ============ Visit Profile ============
  async function visitProfile(publicId, csrfToken) {
    try {
      const resp = await voyagerFetch(
        `/identity/profiles/${publicId}/profileView`,
        { csrfToken }
      );
      if (resp.ok) {
        return { success: true, action: 'visit', publicId };
      }
      return { success: false, error: `Profile visit failed: ${resp.status}`, publicId };
    } catch (e) {
      return { success: false, error: e.message, publicId };
    }
  }

  // ============ Tracking ID Generator ============
  function generateTrackingId() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let result = '';
    for (let i = 0; i < 16; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result + '==';
  }

  // ============ Personalize Message ============
  function personalizeMessage(template, prospect) {
    if (!template) return '';
    let msg = template;
    msg = msg.replace(/\{\{name\}\}/gi, prospect.name || '');
    msg = msg.replace(/\{\{first_name\}\}/gi, (prospect.name || '').split(' ')[0] || '');
    msg = msg.replace(/\{\{company\}\}/gi, prospect.company || '');
    msg = msg.replace(/\{\{title\}\}/gi, prospect.title || '');
    msg = msg.replace(/\{\{location\}\}/gi, prospect.location || '');
    return msg.trim();
  }

  // ============ Message Handler from Background ============
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'EXECUTE_TASK') {
      handleTask(msg.task, msg.csrfToken).then(sendResponse);
      return true; // async
    }
    if (msg.type === 'PING') {
      sendResponse({ alive: true });
      return false;
    }
  });

  async function handleTask(task, csrfToken) {
    const csrf = getCsrfToken(csrfToken);
    const publicId = task.target_public_id || extractPublicId(task.target_profile_url);
    
    if (!publicId) {
      return { success: false, error: 'Could not determine LinkedIn public ID' };
    }

    // Personalize the message
    const message = personalizeMessage(task.message, task.prospect || {});

    switch (task.type) {
      case 'connect':
        return sendConnectionRequest(publicId, message, csrf);
      case 'message':
        return sendMessage(publicId, message, csrf);
      case 'visit':
        return visitProfile(publicId, csrf);
      default:
        return { success: false, error: `Unknown task type: ${task.type}` };
    }
  }

  // ============ Extract Public ID from URL ============
  function extractPublicId(url) {
    if (!url) return null;
    const match = url.match(/linkedin\.com\/in\/([^/?#]+)/);
    return match ? match[1] : null;
  }

  console.log('[LinkedLeads.ai] Content script loaded on LinkedIn');
})();
